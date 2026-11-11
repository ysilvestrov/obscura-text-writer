"""MCP-BRIDGE (#105): the workspace learns about scene changes made elsewhere from a light revisions endpoint."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def _view_revisions(client, story_id):
    return {s['id']: s['revision'] for s in client.get(f'/api/stories/{story_id}').json()['scenes']}


@pytest.mark.req('MCP-BRIDGE')
def test_scene_revisions_follow_the_story_view(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Твір'}).json()
        url = f'/api/stories/{story["id"]}/scene-revisions'
        assert client.get(url).json() == {'scenes': {}}
        first = client.post(f'/api/stories/{story["id"]}/scenes', json={'title': 'Перша'}).json()
        second = client.post(f'/api/stories/{story["id"]}/scenes', json={'title': 'Друга'}).json()
        assert client.get(url).json()['scenes'] == _view_revisions(client, story['id'])
        ref = app.state.repo.save_version(story['id'], first['id'], 'draft', 'Чернетка ззовні', [])
        moved = app.state.repo.set_head(first['id'], 'draft', ref.id, first['revision'])
        revisions = client.get(url).json()['scenes']
        assert revisions[first['id']] == moved.revision > first['revision']
        assert revisions == _view_revisions(client, story['id'])
        trashed = client.post(f'/api/scenes/{second["id"]}/trash', json={'story_id': story['id'], 'expected_revision': second['revision']})
        assert trashed.status_code == 200
        assert client.get(url).json()['scenes'] == _view_revisions(client, story['id']) == {first['id']: moved.revision}


@pytest.mark.req('MCP-BRIDGE')
def test_scene_revisions_reject_unknown_and_trashed_stories(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/stories/missing/scene-revisions').status_code == 404
        story = client.post('/api/stories', json={'title': 'Твір'}).json()
        assert client.post(f'/api/stories/{story["id"]}/trash', json={'expected_revision': story['revision']}).status_code == 200
        assert client.get(f'/api/stories/{story["id"]}/scene-revisions').status_code == 404


@pytest.mark.req('MCP-BRIDGE')
def test_scene_revisions_read_old_payloads_without_revision_as_zero(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Твір'}).json()
        scene = client.post(f'/api/stories/{story["id"]}/scenes', json={'title': 'Сцена'}).json()
        with app.state.repo.db.connection() as db:
            db.execute("UPDATE scenes SET payload=json_remove(payload,'$.revision') WHERE id=?", (scene['id'],))
        assert client.get(f'/api/stories/{story["id"]}/scene-revisions').json()['scenes'] == _view_revisions(client, story['id']) == {scene['id']: 0}
