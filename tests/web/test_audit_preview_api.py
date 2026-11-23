"""R-44 PR 4: `POST /api/stories/{id}/audit/preview` — the read-only audit plan with its upper bound on cost."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.billing.service import set_limit
from storygen.providers.models import ProviderSettings
from storygen.web.app import create_app
from tests.generation.test_audit_context import auditor
from tests.generation.test_audit_cost import tariff
from tests.generation.test_audit_verdict import unchecked_scene

EMPTY_COST = {'per_call_usd': None, 'total_usd': None, 'reason': None}


def app_for(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    return create_app(AppSettings(data_dir=tmp_path)), story, scene


def rows(app):
    with app.state.repo.db.connection() as db:
        return {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('app_settings', 'runs')}


def test_scene_preview_lists_links_calls_fingerprint_and_cost(tmp_path):
    app, story, scene = app_for(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.post(f'/api/stories/{story.id}/audit/preview', json={'scope': 'scene', 'scene_id': scene.id})
        assert response.status_code == 200
        body = response.json()
        assert body['ready'] is True and body['calls'] == 2 and len(body['plan_fingerprint']) == 64
        assert [link['link'] for link in body['links']] == ['brief', 'prose']
        assert body['cost'] == EMPTY_COST
        readiness = client.get(f'/api/stories/{story.id}/readiness',
                               params={'scene_id': scene.id, 'operation': 'audit'}).json()['operations']['audit']
        assert body == readiness


def test_story_preview_covers_the_book(tmp_path):
    app, story, scene = app_for(tmp_path)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        body = client.post(f'/api/stories/{story.id}/audit/preview', json={'scope': 'story'}).json()
    assert body['ready'] is True and body['calls'] == 2 and body['invalid_scenes'] == 1
    assert [(link['scene_id'], link['link']) for link in body['links']] == [(scene.id, 'brief'), (scene.id, 'prose')]
    assert body['cost'] == EMPTY_COST


def test_cloud_preview_carries_the_upper_bound(tmp_path):
    app, story, scene = app_for(tmp_path)
    repo = app.state.repo
    auditor(repo, story, provider=ProviderSettings(provider='openrouter', model='cloud-model'), max_input_chars=1000,
            max_output_tokens=1000)
    tariff(repo)
    set_limit(repo, 'story:' + story.id, '10', 0)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        body = client.post(f'/api/stories/{story.id}/audit/preview', json={'scope': 'story'}).json()
    assert body['ready'] is True, body['reason']
    assert body['cost'] == {'per_call_usd': '0.0063', 'total_usd': '0.0126', 'reason': None}


def test_preview_writes_nothing(tmp_path):
    app, story, scene = app_for(tmp_path)
    before = rows(app)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        assert client.post(f'/api/stories/{story.id}/audit/preview',
                           json={'scope': 'scene', 'scene_id': scene.id}).status_code == 200
        assert client.post(f'/api/stories/{story.id}/audit/preview', json={'scope': 'story'}).status_code == 200
    assert rows(app) == before


def test_scope_and_scene_must_match(tmp_path):
    app, story, scene = app_for(tmp_path)
    url = f'/api/stories/{story.id}/audit/preview'
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        assert client.post(url, json={'scope': 'scene'}).status_code == 422
        assert client.post(url, json={'scope': 'story', 'scene_id': scene.id}).status_code == 422
        assert client.post(url, json={'scope': 'book'}).status_code == 422
        assert client.post('/api/stories/missing/audit/preview', json={'scope': 'story'}).status_code == 404
