import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app

Q = {'role': 'writer', 'provider': 'openrouter', 'model': 'x/y'}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1')


def add_refusal(client, **extra):
    from storygen.providers.models import ProviderSettings
    from storygen.providers.policy import endpoint
    s = ProviderSettings(provider='openrouter', model='x/y')
    entry = {'rating': [0, 2, 1], 'at': '2026-11-12T10:00:00+00:00', 'story_id': 'st1', 'scene_id': 'sc1',
        'attempt_id': 'at1', 'category': 'content_policy', **extra}
    client.app.state.repo.model_policy('add_refusal', entry=entry, role='writer', provider='openrouter',
        base_url=endpoint(s), model='x/y')


@pytest.mark.req('MODEL-003')
def test_consent_roundtrip(client):
    assert client.get('/api/model-policy', params=Q).json() == {'consent': None, 'refusals': []}
    assert client.put('/api/model-policy/consent', json=Q).json()['consent']['consented_at']
    assert client.get('/api/model-policy', params=Q).json()['consent']['consented_at']
    assert client.delete('/api/model-policy/consent', params=Q).json()['consent'] is None


@pytest.mark.req('MODEL-004')
def test_refusal_is_listed_and_cleared(client):
    add_refusal(client)
    body = client.get('/api/model-policy', params=Q).json()
    assert body['refusals'] == [{'rating': [0, 2, 1], 'at': '2026-11-12T10:00:00+00:00', 'category': 'content_policy',
        'story_id': 'st1', 'scene_id': 'sc1'}]
    assert client.delete('/api/model-policy/refusal', params=Q).json()['refusals'] == []
    assert client.get('/api/model-policy', params=Q).json()['refusals'] == []


def test_unknown_role_is_rejected(client):
    assert client.get('/api/model-policy', params={'role': 'evaluator', 'provider': 'venice', 'model': 'm'}).status_code == 400


def test_invalid_provider_settings_are_rejected(client):
    r = client.get('/api/model-policy', params={**Q, 'provider': 'nope'})
    assert r.status_code in (400, 422)
    r = client.put('/api/model-policy/consent', json={**Q, 'provider': 'openrouter', 'base_url': 'http://evil.example'})
    assert r.status_code == 400


def test_response_carries_no_secret_or_text(client, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-secret-value-123')
    add_refusal(client)
    client.put('/api/model-policy/consent', json=Q)
    text = json.dumps(client.get('/api/model-policy', params=Q).json())
    assert 'sk-secret-value-123' not in text and 'attempt_id' not in text and 'at1' not in text
