from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.domain import StoryCreate, SceneCreate


def test_copyedit_http_selection_and_conflicts(tmp_path):
    from tests.generation.test_copyedit_review import generate
    repo, scene, _, attempt = generate(tmp_path)
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        url = f'/api/scenes/{scene.id}/copyedits/{attempt.id}'
        preview = client.get(url).json()
        assert preview['can_apply'] and len(preview['edits']) == 2
        body = dict(expected_revision=preview['expected_revision'], proposal_fingerprint=preview['proposal_fingerprint'], selected_indices=[0])
        result = client.post(url, json=body)
        assert result.status_code == 200
        assert client.post(url, json=body).status_code == 409
        current = repo.get_scene(scene.id)
        assert 'ваша провина' in repo.read_text(current.heads['prose'])
        foreign = repo.create_story(StoryCreate(title='Чужий'))
        other = repo.create_scene(foreign.id, SceneCreate(title='Інша'))
        assert client.get(f'/api/scenes/{other.id}/copyedits/{attempt.id}').status_code == 400
        assert client.get(f'/api/scenes/{scene.id}/copyedits').json()['attempts'][0]['id'] == attempt.id


def test_language_api_only_saved_prose_kinds(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Мова'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    prose = repo.save_version(story.id, scene.id, 'draft', 'Це не ваші провина.', [])
    prompt = repo.save_version(story.id, None, 'prompt', 'Не аналізуй.', [])
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.get(f'/api/versions/{prose.id}/language-warnings')
        assert response.status_code == 200
        assert response.json()['warnings'][0]['quote'] == 'ваші провина'
        assert client.get(f'/api/versions/{prompt.id}/language-warnings').status_code == 400
