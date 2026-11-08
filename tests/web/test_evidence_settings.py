import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app


@pytest.mark.parametrize('role,setting,value,marker', [
    ('memory', 'memory_mode', 'evidence_delta', 'evidence_ids'),
    ('editor', 'edit_mode', 'patches', 'fragment_id'),
])
def test_settings_roundtrip_modes_and_effective_default_prompt(tmp_path, role, setting, value, marker):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Режими'}).json()
        response = client.put(f"/api/stories/{story['id']}/settings", json={
            'expected_revision': story['revision'], 'role': role,
            'settings': {'provider': {'model': 'fake'}, setting: value}, 'prompt_text': '',
        })
        assert response.status_code == 200
        actual = client.get(f"/api/stories/{story['id']}/settings").json()
        assert actual['roles'][role][setting] == value
        assert actual['roles'][role]['prompt_version_id'] is None
        assert marker in actual['prompts'][role]


def _v2_memory_story(tmp_path):
    from storygen.domain import PromptContract
    app = create_app(AppSettings(data_dir=tmp_path))
    client = TestClient(app, base_url='http://127.0.0.1:8765')
    client.__enter__()
    repo = app.state.repo
    story = client.post('/api/stories', json={'title': 'Власний v2'}).json()
    prompt = repo.save_version(story['id'], None, 'prompt', 'Власний промпт пам’яті v2.', [],
                               prompt_contract=PromptContract(stage='memory', mode='evidence_delta', schema_version=2))
    settings = {'provider': {'model': 'fake'}, 'memory_mode': 'evidence_delta', 'prompt_version_id': prompt.id}
    story = repo.write_role_settings(story['id'], {'memory': {**settings, 'provider': {'model': 'fake'}}}, story['revision'])
    return client, story.id, settings


def _saved_contract(client, story_id):
    return client.get(f'/api/stories/{story_id}/settings').json()['prompt_contracts']['memory']


@pytest.mark.parametrize('change', [
    {'prompt_text': 'Змінений власний промпт пам’яті v2.'},
    {'confirm_prompt_contract': True},
])
def test_custom_v2_memory_prompt_keeps_v2_contract_on_save(tmp_path, change):
    client, story_id, settings = _v2_memory_story(tmp_path)
    try:
        revision = client.get(f'/api/stories/{story_id}/settings').json()['story']['revision']
        response = client.put(f'/api/stories/{story_id}/settings', json={
            'expected_revision': revision, 'role': 'memory', 'settings': settings, **change})
        assert response.status_code == 200, response.text
        actual = client.get(f'/api/stories/{story_id}/settings').json()
        assert actual['prompt_contracts']['memory'] == {'stage': 'memory', 'mode': 'evidence_delta', 'schema_version': 2}
    finally:
        client.__exit__(None, None, None)


def test_new_custom_memory_prompt_and_standard_reset_get_v3(tmp_path):
    client, story_id, settings = _v2_memory_story(tmp_path)
    try:
        revision = client.get(f'/api/stories/{story_id}/settings').json()['story']['revision']
        response = client.put(f'/api/stories/{story_id}/settings', json={
            'expected_revision': revision, 'role': 'memory', 'settings': settings, 'prompt_text': ''})
        assert response.status_code == 200, response.text
        assert _saved_contract(client, story_id)['schema_version'] == 3
        revision = response.json()['revision']
        response = client.put(f'/api/stories/{story_id}/settings', json={
            'expected_revision': revision, 'role': 'memory', 'settings': {**settings, 'prompt_version_id': None},
            'prompt_text': 'Новий власний промпт.'})
        assert response.status_code == 200, response.text
        assert _saved_contract(client, story_id) == {'stage': 'memory', 'mode': 'evidence_delta', 'schema_version': 3}
    finally:
        client.__exit__(None, None, None)


def test_settings_label_agrees_with_stored_contract(tmp_path):
    """The settings.js label (expectedPromptContract) must predict what the server stores."""
    import shutil, subprocess
    from pathlib import Path
    node = shutil.which('node')
    if node is None:
        pytest.skip('node недоступний')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, str(root / 'tests/web/js/prompt_contract_label.mjs')],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr


def _put(client, story_id, **body):
    revision = client.get(f'/api/stories/{story_id}/settings').json()['story']['revision']
    return client.put(f'/api/stories/{story_id}/settings', json={'expected_revision': revision, **body})


@pytest.mark.parametrize('change', [
    {'prompt_text': 'Новий текст для v3.'},
    {'confirm_prompt_contract': True},
])
def test_upgrade_memory_wire_saves_v3_contract(tmp_path, change):
    client, story_id, settings = _v2_memory_story(tmp_path)
    try:
        response = _put(client, story_id, role='memory', settings=settings, upgrade_memory_wire=True, **change)
        assert response.status_code == 200, response.text
        contract = _saved_contract(client, story_id)
        assert contract == {'stage': 'memory', 'mode': 'evidence_delta', 'schema_version': 3}
        assert client.get(f'/api/stories/{story_id}/settings').json()['roles']['memory']['prompt_version_id']
    finally:
        client.__exit__(None, None, None)


@pytest.mark.parametrize('standard', [False, True])
def test_upgrade_with_standard_or_blank_text_returns_builtin(tmp_path, standard):
    from storygen.generation.prompts import role_prompt
    from storygen.providers.models import RoleSettings
    client, story_id, settings = _v2_memory_story(tmp_path)
    try:
        text = role_prompt('memory', RoleSettings.model_validate(settings)) if standard else ''
        response = _put(client, story_id, role='memory', settings=settings, upgrade_memory_wire=True, prompt_text=text)
        assert response.status_code == 200, response.text
        assert client.get(f'/api/stories/{story_id}/settings').json()['roles']['memory']['prompt_version_id'] is None
        assert _saved_contract(client, story_id)['schema_version'] == 3
    finally:
        client.__exit__(None, None, None)


def test_upgrade_rejected_for_non_memory_role_or_snapshot(tmp_path):
    client, story_id, settings = _v2_memory_story(tmp_path)
    try:
        r = _put(client, story_id, role='writer', settings={'provider': {'model': 'fake'}},
                 prompt_text='Власний writer.', upgrade_memory_wire=True)
        assert r.status_code == 400
        r = _put(client, story_id, role='memory', settings={**settings, 'memory_mode': 'snapshot'},
                 prompt_text='Власний.', upgrade_memory_wire=True)
        assert r.status_code == 400
        assert _saved_contract(client, story_id)['schema_version'] == 2
    finally:
        client.__exit__(None, None, None)


def test_v2_prompt_without_upgrade_stays_v2(tmp_path):
    client, story_id, settings = _v2_memory_story(tmp_path)
    try:
        assert _put(client, story_id, role='memory', settings=settings, prompt_text='Інший.').status_code == 200
        assert _saved_contract(client, story_id)['schema_version'] == 2
    finally:
        client.__exit__(None, None, None)


def test_contract_follows_incoming_prompt_version_id(tmp_path):
    """Stored role settings point at /2, but the request points at another /3 prompt: the /3 contract is kept."""
    from storygen.domain import PromptContract
    client, story_id, settings = _v2_memory_story(tmp_path)
    try:
        repo = client.app.state.repo
        v3 = repo.save_version(story_id, None, 'prompt', 'Власний v3.', [],
                               prompt_contract=PromptContract(stage='memory', mode='evidence_delta', schema_version=3))
        response = _put(client, story_id, role='memory', settings={**settings, 'prompt_version_id': v3.id},
                        prompt_text='Правка v3.')
        assert response.status_code == 200, response.text
        assert _saved_contract(client, story_id)['schema_version'] == 3
    finally:
        client.__exit__(None, None, None)


def test_edit_with_other_story_v2_prompt_id_is_rejected(tmp_path):
    from storygen.domain import PromptContract
    client, story_id, settings = _v2_memory_story(tmp_path)
    try:
        repo = client.app.state.repo
        other = client.post('/api/stories', json={'title': 'Чужа'}).json()
        foreign = repo.save_version(other['id'], None, 'prompt', 'Чужий v2.', [],
                                    prompt_contract=PromptContract(stage='memory', mode='evidence_delta', schema_version=2))
        for extra in ({}, {'upgrade_memory_wire': True}):
            response = _put(client, story_id, role='memory', settings={**settings, 'prompt_version_id': foreign.id},
                            prompt_text='Правка.', **extra)
            assert response.status_code == 400, response.text
            assert _saved_contract(client, story_id)['schema_version'] == 2
    finally:
        client.__exit__(None, None, None)
