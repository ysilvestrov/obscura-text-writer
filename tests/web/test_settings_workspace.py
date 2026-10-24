import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('script',['settings_workspace.mjs','evaluator_settings.mjs','settings_controller.mjs'])
def test_settings_workspace_regressions(script):
    node=shutil.which('node')
    if not node:pytest.skip('Node required')
    result=subprocess.run([node,str(Path(__file__).parent/'js'/script)],capture_output=True,encoding='utf8',timeout=20)
    assert result.returncode==0,result.stderr


def test_settings_page_exposes_sections_without_json_only_evaluator(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Налаштування'}).json()
        page=client.get(f'/stories/{story["id"]}/settings').text
        for section in ['writing','models','evaluator','budget','profiles']:
            assert f'data-settings-section="{section}"' in page
        assert 'id="evaluator-settings"' in page and 'id="settings-save"' in page
        assert 'id="settings-section-mobile"' in page
