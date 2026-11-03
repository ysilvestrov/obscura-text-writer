from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate, SceneCreate
from storygen.web.app import create_app


def test_author_format_api_and_structured_boundaries(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path/'data', env_file=tmp_path/'missing.env'))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Спостереження'))
    scene = repo.create_scene(story.id, SceneCreate(title='Парк'))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        result = client.post(f'/api/scenes/{scene.id}/draft', json={
            'text': 'Лєра побачила **зорі**.', 'content_format': 'markdown', 'expected_revision': scene.revision,
        })
        assert result.status_code == 200, result.text
        first = result.json()
        assert first['version']['content_format'] == 'markdown'
        again = client.post(f'/api/scenes/{scene.id}/draft', json={
            'text': 'Лєра побачила **зорі**.', 'expected_revision': first['scene']['revision'],
        })
        assert again.json()['version']['id'] == first['version']['id']
        assert repo.read_text(first['version']['id']) == 'Лєра побачила **зорі**.'
        # JSON and plans do not gain an author-text interpretation field.
        for kind in ('brief', 'memory'):
            invalid = client.post(f'/api/scenes/{scene.id}/{kind}', json={
                'text': '{}', 'content_format': 'markdown', 'expected_revision': first['scene']['revision'],
            })
            assert invalid.status_code == 422
