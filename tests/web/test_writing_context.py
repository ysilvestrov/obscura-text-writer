"""MCP-BRIDGE read endpoints: the story list and the writing context of a scene."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.dependencies import writing_fingerprint
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.web.app import create_app

BRIEF = '{"objective":"Анна йде до маяка","beats":["Анна йде до маяка"],"constraints":[],"proposed_changes":[]}'


def story_with_memory(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    first = repo.create_scene(story.id, SceneCreate(title='Вдома', beats='Вдома', character_ids=['A']))
    second = repo.create_scene(story.id, SceneCreate(title='Маяк', beats='Маяк і стара карта', character_ids=['A']))
    prose = repo.save_version(story.id, first.id, 'manual', 'Анна вдома в халаті.', [])
    repo.set_head(first.id, 'prose', prose.id, repo.get_scene(first.id).revision)
    events = [_add_event('character_states', 'Синій халат', prose.id, 'в халаті', 0, ['A'], slot='clothing'),
              _add_event('facts', 'Маяк стоїть на старій карті', prose.id, 'вдома', 1)]
    journal = MemoryJournal(schema_version=3, source_prose_ids=[prose.id], events=events)
    memory = repo.save_version(story.id, first.id, 'memory', journal.model_dump_json(), [prose.id])
    repo.set_head(first.id, 'memory', memory.id, repo.get_scene(first.id).revision)
    brief = repo.save_version(story.id, second.id, 'brief', BRIEF, [])
    repo.set_head(second.id, 'brief', brief.id, repo.get_scene(second.id).revision)
    return app, repo, story, repo.get_scene(second.id)


@pytest.mark.req('MCP-BRIDGE')
def test_writing_context_of_scene_without_own_memory_matches_draft_context(tmp_path):
    app, repo, story, scene = story_with_memory(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.get(f'/api/scenes/{scene.id}/writing-context')
    assert response.status_code == 200, response.text
    data = response.json()
    bundle = build_context(repo, scene.id, 'draft', RoleSettings(provider=ProviderSettings(model='test'), context_tokens=262144))
    assert 'Маяк стоїть на старій карті' in data['memory']
    assert data['memory'] in bundle.user_text
    assert data['brief'] == BRIEF and data['plan'] == 'Маяк і стара карта'
    assert data['revision'] == scene.revision and data['language'] == 'uk' and data['position'] == 1
    assert data['context_fingerprint'] == writing_fingerprint(repo, scene)
    assert 'system' not in data and 'prompt' not in str(data.keys())


@pytest.mark.req('MCP-BRIDGE')
def test_story_list_skips_the_bin(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    kept = repo.create_story(StoryCreate(title='Лишається'))
    repo.create_scene(kept.id, SceneCreate(title='Одна'))
    gone = repo.create_story(StoryCreate(title='У кошику'))
    repo.set_story_trashed(gone.id, gone.revision, False)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.get('/api/stories')
    assert response.status_code == 200, response.text
    rating = repo.get_story(kept.id).content_rating
    assert response.json() == [{'id': kept.id, 'title': 'Лишається', 'language': 'uk', 'rating': rating.model_dump() if rating else None, 'writing_mode': 'chat', 'scene_count': 1}]


def test_store_edition_checks_the_rating_of_the_returned_context(tmp_path, store_edition, monkeypatch):
    # The limit is applied to the snapshot that is returned, not to a separate earlier read of the scene.
    from storygen.application import writing_context as module
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист', beats='Анна знаходить лист.'))
    original = module._read

    def raised_meanwhile(repo, scene_id):
        scene, content, fingerprint = original(repo, scene_id)
        return scene, {**content, 'rating': {'sexual': 2, 'violence': 0, 'themes': 0}}, fingerprint
    monkeypatch.setattr(module, '_read', raised_meanwhile)
    with pytest.raises(ValueError, match='найвищий дозволений рівень — 1'):
        module.writing_context(repo, scene.id)
