"""CHARACTER-EXTRACT (R-51): `POST /api/stories/{id}/character-extract/preview` — the read-only run plan."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.web.app import create_app
from tests.generation.test_memory_build import written_book

WORDS = ' '.join(['слово'] * 600) + '.'


def tables(app):
    with app.state.repo.db.connection() as db:
        return {name: db.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
                for name in ('app_settings', 'runs', 'versions', 'run_events')}


@pytest.mark.req('CHARACTER-EXTRACT')
def test_preview_route_writes_nothing(tmp_path):
    repo, story, scenes = written_book(tmp_path, [WORDS] * 2, memory_role=RoleSettings(
        provider=ProviderSettings(model='memory'), context_tokens=32768))
    app = create_app(AppSettings(data_dir=tmp_path))
    before = tables(app)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.post(f'/api/stories/{story.id}/character-extract/preview', json={'group_words': 1000})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['ready'] is True and body['groups'] == [[s.id] for s in scenes] and body['calls_bound'] == 6
        assert set(body) >= {'reason', 'scenes_count', 'skipped', 'cost', 'cards_count', 'has_protagonist',
                             'pending_proposal', 'plan_fingerprint'}
        assert client.post(f'/api/stories/{story.id}/character-extract/preview', json={}).json()['groups'] == \
            [[s.id for s in scenes]]
        assert client.post(f'/api/stories/{story.id}/character-extract/preview', json={'group_words': 10}).status_code == 422
        assert client.post('/api/stories/missing/character-extract/preview', json={}).status_code == 404
    assert tables(app) == before
