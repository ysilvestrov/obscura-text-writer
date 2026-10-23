import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.web.app import create_app


def workspace(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Ручна чернетка'))
    scene = repo.create_scene(story.id, SceneCreate(title='Перша сцена'))
    return app, repo, story, scene


def test_manual_draft_is_versioned_and_available_to_editor(tmp_path):
    app, repo, story, scene = workspace(tmp_path)
    text = 'Олена відчинила двері.\n\n— Добрий день, — сказала вона.'
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        result = client.post(f'/api/scenes/{scene.id}/draft', json={
            'text': text, 'expected_revision': scene.revision,
        })
        assert result.status_code == 200, result.text
        saved = result.json()
        assert saved['version']['kind'] == 'draft'
        assert saved['version']['source_run_id'] is None
        assert saved['scene']['revision'] == scene.revision + 1
        assert saved['scene']['heads']['draft'] == saved['version']['id']
        assert 'prose' not in saved['scene']['heads']
        assert repo.read_text(saved['version']['id']) == text
        context = build_context(repo, scene.id, 'edit', RoleSettings(
            provider=ProviderSettings(model='test'), edit_mode='patches',
        ))
        assert saved['version']['id'] in context.input_refs
        assert 'Олена відчинила двері.' in context.user_text
        assert repo.get_story(story.id).revision > story.revision


def test_manual_draft_conflict_preserves_head_and_history_and_invalidates_dependents(tmp_path):
    app, repo, story, scene = workspace(tmp_path)
    old = repo.save_version(story.id, scene.id, 'draft', 'Попередня чернетка.', [])
    scene = repo.set_head(scene.id, 'draft', old.id, scene.revision)
    edited = repo.save_version(story.id, scene.id, 'edited', 'Попередня проза.', [old.id])
    scene = repo.set_head(scene.id, 'prose', edited.id, scene.revision)
    memory = repo.save_version(story.id, scene.id, 'memory', '{}', [edited.id])
    scene = repo.set_head(scene.id, 'memory', memory.id, scene.revision)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.post(f'/api/scenes/{scene.id}/draft', json={
            'text': 'Нова ручна чернетка.', 'expected_revision': scene.revision,
        })
        assert response.status_code == 200, response.text
        new_id = response.json()['version']['id']
        conflict = client.post(f'/api/scenes/{scene.id}/draft', json={
            'text': 'Правка з іншої вкладки.', 'expected_revision': scene.revision,
        })
        assert conflict.status_code == 409
        current = repo.get_scene(scene.id)
        assert current.heads == {'draft': new_id, 'prose': edited.id, 'memory': memory.id}
        assert current.needs_review
        assert repo.get_version(edited.id).stale
        assert repo.get_version(memory.id).stale
        assert not repo.get_version(new_id).stale
        assert repo.read_text(old.id) == 'Попередня чернетка.'
        assert {repo.read_text(v.id) for v in repo.list_versions(story.id, scene.id, 'draft')} == {
            'Попередня чернетка.', 'Нова ручна чернетка.', 'Правка з іншої вкладки.',
        }


@pytest.mark.parametrize('text', ['', ' \n\t '])
def test_blank_manual_draft_is_rejected_without_version(tmp_path, text):
    app, repo, story, scene = workspace(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        result = client.post(f'/api/scenes/{scene.id}/draft', json={
            'text': text, 'expected_revision': scene.revision,
        })
        assert result.status_code == 400
        assert repo.get_scene(scene.id).heads == {}
        assert repo.list_versions(story.id, scene.id) == []

@pytest.mark.parametrize('mode',['draft','prose'])
def test_manual_text_after_hidden_memory_is_fresh_without_revalidating_old_versions(tmp_path,mode):
    from tests.memory.test_forwarding import seeded,apply
    from storygen.memory.forwarding import memory_view
    repo,story,scenes=seeded(tmp_path)
    claim=memory_view(repo,scenes[1].id)['rows'][0]['claim_id']
    apply(repo,scenes[1],{claim:False})
    target=repo.get_scene(scenes[2].id);old=target.heads['prose']
    assert repo.context_view(story.id).get_version(old).stale
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        response=client.post(f'/api/scenes/{target.id}/{mode}',json={'text':'Нова ручна версія.','expected_revision':target.revision})
        assert response.status_code==200,response.text
        ref=repo.get_version(response.json()['version']['id'])
        assert not ref.stale and ref.manual_projection_policy==[claim]
        assert repo.context_view(story.id).get_version(old).stale
        apply(repo,repo.get_scene(scenes[1].id),{claim:True})
        assert repo.get_version(ref.id).stale
        if mode=='prose':assert repo.get_scene(target.id).needs_review
        apply(repo,repo.get_scene(scenes[1].id),{claim:False})
        assert not repo.get_version(ref.id).stale
        conflict=client.post(f'/api/scenes/{target.id}/{mode}',json={'text':'Конфліктна правка.','expected_revision':target.revision})
        assert conflict.status_code==409


def test_manual_prose_policy_does_not_hide_review_after_story_style_changes(tmp_path):
    from storygen.generation.dependencies import save_manual_prose
    app,repo,story,scene=workspace(tmp_path)
    save_manual_prose(repo,scene.id,'Ручний текст.',scene.revision)
    ref=repo.save_version(story.id,None,'style','Стиль',[])
    repo.publish_story_material(story.id,'style_version_id',ref.id,repo.get_story(story.id).revision)
    assert repo.get_scene(scene.id).needs_review
