import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.web.app import create_app


def test_accept_completed_draft_preserves_exact_version_and_cas(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Прийняття'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    draft = repo.save_version(story.id, scene.id, 'draft', 'Уже отриманий текст.', [])
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.post(f'/api/scenes/{scene.id}/accept-draft', json={
            'version_id': draft.id, 'expected_revision': scene.revision,
        })
        assert response.status_code == 200, response.text
        assert response.json()['heads']['draft'] == draft.id
        assert len(repo.list_versions(story.id, scene.id, 'draft')) == 1
        conflict = client.post(f'/api/scenes/{scene.id}/accept-draft', json={
            'version_id': draft.id, 'expected_revision': scene.revision,
        })
        assert conflict.status_code == 409


@pytest.mark.parametrize('invalid', ['wrong-kind', 'other-scene', 'stale', 'incomplete'])
def test_accept_draft_rejects_ineligible_versions(tmp_path, invalid):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Прийняття'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    owner = repo.create_scene(story.id, SceneCreate(title='Інша')) if invalid == 'other-scene' else scene
    ref = repo.save_version(story.id, owner.id, 'manual' if invalid == 'wrong-kind' else 'draft', 'Текст.', [])
    if invalid in {'stale', 'incomplete'}:
        ref.stale = invalid == 'stale'
        ref.complete = invalid != 'incomplete'
        with repo.db.connection() as db:
            db.execute('UPDATE versions SET payload=? WHERE id=?', (ref.model_dump_json(), ref.id))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.post(f'/api/scenes/{scene.id}/accept-draft', json={
            'version_id': ref.id, 'expected_revision': scene.revision,
        })
        assert response.status_code == 400
        assert 'draft' not in repo.get_scene(scene.id).heads
