import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app


@pytest.mark.parametrize('role,setting,value,marker', [
    ('memory', 'memory_mode', 'evidence_delta', 'evidence_id'),
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
