"""R-48 PR 2 (design §5): `GET /api/stories/{id}/memory-build` — the scene the memory build starts from and its size."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.generation.test_memory_build import give_memory, written_book


def test_memory_build_route_returns_target_and_count(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.', 'Третя.'])
    give_memory(repo, story, scenes[0])
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.get(f'/api/stories/{story.id}/memory-build')
        assert response.status_code == 200
        assert response.json() == {'scene_id': scenes[1].id, 'count': 2}
        for scene in scenes[1:]:
            give_memory(app.state.repo, story, scene)
        assert client.get(f'/api/stories/{story.id}/memory-build').json() == {'scene_id': None, 'count': 0}
        assert client.get('/api/stories/missing/memory-build').status_code == 404
