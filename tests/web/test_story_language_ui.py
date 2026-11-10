import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate
from storygen.web.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        yield client


@pytest.mark.req('STORY-LANGUAGE')
def test_story_view_reports_language_lock(client):
    story = client.post('/api/stories', json={'title': 'Pier', 'language': 'en'}).json()
    view = client.get(f'/api/stories/{story["id"]}').json()
    assert view['story']['language'] == 'en' and view['language_locked'] is False
    repo = client.app.state.repo
    scene = repo.create_scene(story['id'], SceneCreate(title='Pier', beats='x'))
    repo.save_version(story['id'], scene.id, 'brief', '{}', [], 'run-1')
    assert client.get(f'/api/stories/{story["id"]}').json()['language_locked'] is True


@pytest.mark.req('STORY-LANGUAGE')
def test_language_lock_helper_matches_server_refusal(client):
    story = client.post('/api/stories', json={'title': 'Pier'}).json()
    repo = client.app.state.repo
    scene = repo.create_scene(story['id'], SceneCreate(title='Pier', beats='x'))
    repo.save_version(story['id'], scene.id, 'brief', '{}', [], 'run-1')
    revision = repo.get_story(story['id']).revision
    response = client.put(f'/api/stories/{story["id"]}/language', json={'language': 'en', 'expected_revision': revision})
    assert response.status_code == 409
    assert client.get(f'/api/stories/{story["id"]}').json()['language_locked'] is True
