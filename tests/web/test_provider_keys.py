"""SECURITY-002: a provider key can be given to the server, is kept only in the OS store and never comes back."""
import logging

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import StoryCreate
from storygen.providers import secrets
from storygen.providers.client import build_openai_client
from storygen.providers.models import ProviderSettings
from storygen.web.app import create_app

VALUE = 'sk-test-12345-synthetic'
NAME = 'OPENROUTER_API_KEY'
URL = f'/api/provider-keys/{NAME}'


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ('OPENROUTER_API_KEY', 'VENICE_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    return TestClient(app, base_url='http://127.0.0.1')


def state(source, stored, available=True):
    return {'name': NAME, 'source': source, 'stored': stored, 'store_available': available}


def test_state_put_delete_roundtrip(client, secret_store, monkeypatch):
    assert client.get(URL).json() == state(None, False)
    saved = client.put(URL, json={'value': VALUE})
    assert saved.status_code == 200 and saved.json() == state('store', True)
    assert secret_store.items == {NAME: VALUE}
    monkeypatch.setenv(NAME, 'from-env')
    assert client.get(URL).json() == state('env', True)
    monkeypatch.delenv(NAME)
    assert client.delete(URL).json() == state(None, False)
    assert client.delete(URL).json() == state(None, False)


def test_saved_key_is_used_without_restart(client, secret_store):
    client.put(URL, json={'value': f'  {VALUE}\n'})
    assert build_openai_client(ProviderSettings(provider='openrouter', model='m')).api_key == VALUE


def test_value_never_appears_in_responses_files_or_logs(client, secret_store, tmp_path, caplog):
    repo = client.app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    with caplog.at_level(logging.DEBUG):
        bodies = [client.put(URL, json={'value': VALUE}).text, client.get(URL).text,
                  client.get(f'/api/stories/{story.id}/settings').text, client.get('/api/app-info').text,
                  client.get(f'/stories/{story.id}/settings').text, client.delete(URL).text]
        client.put(URL, json={'value': VALUE})
    assert all(VALUE not in body for body in bodies)
    assert VALUE not in caplog.text
    leaked = [str(path) for path in (tmp_path / 'data').rglob('*') if path.is_file() and VALUE.encode() in path.read_bytes()]
    assert leaked == []


def test_cross_site_write_is_rejected(client, secret_store):
    response = client.put(URL, json={'value': VALUE}, headers={'Origin': 'https://evil.example'})
    assert response.status_code == 403 and secret_store.items == {}
    assert client.request('DELETE', URL, headers={'Origin': 'https://evil.example'}).status_code == 403


@pytest.mark.parametrize('body', [{'value': ''}, {'value': ' \n '}, {'value': 'x' * 5000}, {}, {'value': 5}, {'value': VALUE, 'extra': 1}])
def test_bad_values_are_rejected_without_echo(client, secret_store, body):
    response = client.put(URL, json=body)
    assert response.status_code in {400, 422} and secret_store.items == {}
    assert VALUE not in response.text and 'xxxxx' not in response.text


@pytest.mark.parametrize('name', ['path', 'lower_key', 'A', 'WITH-DASH', 'X' * 65])
def test_invalid_names_are_rejected(client, secret_store, name):
    for response in (client.get(f'/api/provider-keys/{name}'), client.put(f'/api/provider-keys/{name}', json={'value': VALUE}),
                     client.delete(f'/api/provider-keys/{name}')):
        assert response.status_code == 400, (name, response.status_code)
    assert secret_store.items == {}


def test_unavailable_store_is_reported_and_refuses_writes(client):
    secrets.set_backend(None)
    assert client.get(URL).json() == state(None, False, available=False)
    response = client.put(URL, json={'value': VALUE})
    assert response.status_code == 400
    assert response.json()['detail'] == 'Некоректні дані: Сховище ключів недоступне на цьому комп’ютері. Задайте ключ змінною середовища.'
    english = client.put(URL, json={'value': VALUE}, headers={'accept-language': 'en'}).json()['detail']
    assert english == 'Invalid data: The key store is unavailable on this computer. Set the key in an environment variable.'
