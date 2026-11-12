"""Saving settings rejects a model the catalog says has no JSON Schema support, and never fails on catalog trouble."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate
from storygen.providers import schema_support
from storygen.providers.models import ModelOption, ProviderSettings, RoleSettings
from storygen.web.app import create_app

MESSAGE = 'Модель не підтримує JSON Schema. Виберіть іншу модель або режим „JSON за промптом“.'


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1')


@pytest.fixture
def story_id(client):
    return client.app.state.repo.create_story(StoryCreate(title='Маяк')).id


def catalog(monkeypatch, supports=False, fail=False):
    calls = []

    def fake(settings, http_client=None, *, repo=None):
        calls.append(settings.model)
        if fail:
            raise ValueError('catalog down')
        return [ModelOption(id='m', supports_schema=supports)]
    monkeypatch.setattr(schema_support, 'discover_models', fake)
    return calls


def provider(mode='json_schema', name='venice'):
    return ProviderSettings(provider=name, model='m', response_mode=mode).model_dump()


def save_role(client, story_id, mode='json_schema', name='venice'):
    revision = client.get(f'/api/stories/{story_id}/settings').json()['story']['revision']
    settings = RoleSettings(provider=ProviderSettings(provider=name, model='m', response_mode=mode)).model_dump()
    return client.put(f'/api/stories/{story_id}/settings', json={'expected_revision': revision, 'role': 'writer', 'settings': settings})


def save_shared(client, story_id, mode='json_schema'):
    revision = client.get(f'/api/stories/{story_id}/settings').json()['story']['revision']
    return client.put(f'/api/stories/{story_id}/settings/shared-provider', json={'expected_revision': revision, 'provider': provider(mode)})


def test_save_rejects_known_non_schema_model_in_schema_mode(client, story_id, monkeypatch):
    catalog(monkeypatch, supports=False)
    for response in (save_role(client, story_id), save_shared(client, story_id)):
        assert response.status_code == 400
        assert MESSAGE in response.text


def test_save_allows_when_catalog_unavailable(client, story_id, monkeypatch):
    catalog(monkeypatch, fail=True)
    assert save_role(client, story_id).status_code == 200
    assert save_shared(client, story_id).status_code == 200


def test_save_allows_prompt_json_mode(client, story_id, monkeypatch):
    calls = catalog(monkeypatch, supports=False)
    assert save_role(client, story_id, mode='prompt_json').status_code == 200
    assert save_shared(client, story_id, mode='prompt_json').status_code == 200
    assert calls == []


def test_save_allows_supported_unknown_and_local(client, story_id, monkeypatch):
    catalog(monkeypatch, supports=True)
    assert save_role(client, story_id).status_code == 200
    catalog(monkeypatch, supports=None)
    assert save_role(client, story_id).status_code == 200
    calls = catalog(monkeypatch, supports=False)
    assert save_role(client, story_id, name='local').status_code == 200
    assert calls == []


def test_schema_mismatch_ignores_unexpected_catalog_errors(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError('boom')
    monkeypatch.setattr(schema_support, 'discover_models', boom)
    assert schema_support.schema_mismatch(ProviderSettings(provider='venice', model='m', response_mode='json_schema')) is None


def test_rejected_save_writes_no_prompt_version(client, story_id, monkeypatch):
    catalog(monkeypatch, supports=False)
    repo = client.app.state.repo
    before = len(repo.list_versions(story_id, kind='prompt'))
    revision = client.get(f'/api/stories/{story_id}/settings').json()['story']['revision']
    settings = RoleSettings(provider=ProviderSettings(provider='venice', model='m', response_mode='json_schema')).model_dump()
    body = {'expected_revision': revision, 'role': 'writer', 'settings': settings, 'prompt_text': 'Власний промпт для перевірки.'}
    assert client.put(f'/api/stories/{story_id}/settings', json=body).status_code == 400
    shared = client.put(f'/api/stories/{story_id}/settings/shared-provider', json={**body, 'provider': provider()})
    assert shared.status_code == 400
    assert len(repo.list_versions(story_id, kind='prompt')) == before
