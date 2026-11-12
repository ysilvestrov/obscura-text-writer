"""Saving settings rejects limits above the caps the catalog reports for the chosen model (MODEL-005-S03)."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate
from storygen.providers import schema_support
from storygen.providers.models import ClassificationSettings, ModelOption, ProviderSettings, RoleSettings, RoleVariant
from storygen.web.app import create_app

OUTPUT = 'Вихідний ліміт 16000 перевищує ліміт вибраної моделі 8192 токенів. Змініть налаштування; автоматичного повтору немає.'
CONTEXT = 'Контекст 65536 перевищує ліміт вибраної моделі 32768 токенів. Змініть налаштування; автоматичного повтору немає.'


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1')


@pytest.fixture
def story_id(client):
    return client.app.state.repo.create_story(StoryCreate(title='Маяк')).id


def catalog(monkeypatch, fail=False, context=32768, output=8192):
    seen = []

    def fake(settings, http_client=None, *, repo=None):
        seen.append(settings)
        if fail:
            raise ValueError('catalog down')
        return [ModelOption(id='m', context_tokens=context, max_output_tokens=output), ModelOption(id='other')]
    monkeypatch.setattr(schema_support, 'discover_models', fake)
    return seen


def venice(model='m'):
    return ProviderSettings(provider='venice', model=model, response_mode='prompt_json')


def revision(client, story_id):
    return client.get(f'/api/stories/{story_id}/settings').json()['story']['revision']


def save(client, story_id, settings, role='writer'):
    return client.put(f'/api/stories/{story_id}/settings', json={'expected_revision': revision(client, story_id), 'role': role, 'settings': settings.model_dump()})


@pytest.mark.req('MODEL-005')
def test_role_limits_above_catalog_caps_are_rejected(client, story_id, monkeypatch):
    seen = catalog(monkeypatch)
    response = save(client, story_id, RoleSettings(provider=venice(), context_tokens=32768, max_output_tokens=16000))
    assert response.status_code == 400 and OUTPUT in response.text
    response = save(client, story_id, RoleSettings(provider=venice(), context_tokens=65536, max_output_tokens=4096))
    assert response.status_code == 400 and CONTEXT in response.text
    assert save(client, story_id, RoleSettings(provider=venice(), context_tokens=32768, max_output_tokens=8192)).status_code == 200
    # An offline catalog must not stall a save for the provider's long generation timeout.
    assert seen and all(item.timeout <= schema_support.CATALOG_TIMEOUT for item in seen)


@pytest.mark.req('MODEL-005')
def test_variant_and_classifier_limits_are_checked_against_their_own_model(client, story_id, monkeypatch):
    catalog(monkeypatch)
    main = dict(provider=venice('other'), context_tokens=65536, max_output_tokens=16000)
    variant = RoleVariant(provider=venice(), context_tokens=32768, max_output_tokens=16000)
    response = save(client, story_id, RoleSettings(**main, low_rating_variant=variant))
    assert response.status_code == 400 and OUTPUT in response.text
    classifier = ClassificationSettings(provider=venice(), context_tokens=65536, max_output_tokens=4096)
    response = save(client, story_id, RoleSettings(**main, classification=classifier), role='editor')
    assert response.status_code == 400 and CONTEXT in response.text
    assert save(client, story_id, RoleSettings(**main)).status_code == 200


@pytest.mark.req('MODEL-005')
def test_shared_provider_checks_every_role_limits(client, story_id, monkeypatch):
    catalog(monkeypatch)
    repo = client.app.state.repo
    assert save(client, story_id, RoleSettings(provider=ProviderSettings(provider='local', model='x'), context_tokens=32768, max_output_tokens=16000), role='editor').status_code == 200
    body = {'expected_revision': revision(client, story_id), 'provider': venice().model_dump()}
    response = client.put(f'/api/stories/{story_id}/settings/shared-provider', json=body)
    assert response.status_code == 400 and OUTPUT in response.text
    assert repo.read_role_settings(story_id)['editor']['provider']['provider'] == 'local'


@pytest.mark.req('MODEL-005')
def test_unknown_caps_unknown_model_local_and_offline_catalog_do_not_block(client, story_id, monkeypatch):
    big = dict(context_tokens=200000, max_output_tokens=100000)
    catalog(monkeypatch, context=None, output=None)
    assert save(client, story_id, RoleSettings(provider=venice(), **big)).status_code == 200
    catalog(monkeypatch)
    assert save(client, story_id, RoleSettings(provider=venice('missing'), **big)).status_code == 200
    seen = catalog(monkeypatch)
    assert save(client, story_id, RoleSettings(provider=ProviderSettings(provider='local', model='m'), **big)).status_code == 200
    assert seen == []
    catalog(monkeypatch, fail=True)
    assert save(client, story_id, RoleSettings(provider=venice(), **big)).status_code == 200
