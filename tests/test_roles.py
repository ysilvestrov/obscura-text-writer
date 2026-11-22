"""MODEL-001-S03: one role registry for the server and the browser."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from storygen.roles import ROLE_LABEL_KEYS, ROLE_LABELS, ROLE_SET, ROLE_STAGE, ROLES, STAGE_ROLE

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'src/storygen/web/static'
LABEL_MAPS = ['role-profiles.js', 'settings-workspace.js', 'settings.js', 'workspace-navigation.js']


def test_role_stage_maps_agree():
    assert set(ROLE_STAGE) == set(ROLES) == ROLE_SET
    assert all(STAGE_ROLE[ROLE_STAGE[role]] == role for role in ROLES)
    assert set(STAGE_ROLE.values()) == ROLE_SET
    assert set(ROLE_LABELS) == set(ROLE_LABEL_KEYS) == ROLE_SET
    catalog = json.loads((STATIC / 'i18n.json').read_text(encoding='utf-8'))
    assert all(key in json.dumps(catalog) for key in ROLE_LABEL_KEYS.values())


def test_settings_page_has_a_button_per_role(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Ролі'}).json()
        page = client.get(f"/stories/{story['id']}/settings").text
    assert [role for role in ROLES if f'data-settings-role="{role}"' in page] == list(ROLES)
    assert page.count('data-settings-role=') == len(ROLES)


def test_browser_registry_matches_server():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки roles.js')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/roles.mjs')], cwd=ROOT, capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'ROLES': list(ROLES), 'ROLE_STAGE': ROLE_STAGE, 'STAGE_ROLE': STAGE_ROLE}


@pytest.mark.parametrize('name', LABEL_MAPS)
def test_every_label_map_names_every_role(name):
    source = (STATIC / name).read_text(encoding='utf-8')
    for role in ROLES:
        assert f'get {role}()' in source, (name, role)


def test_no_inline_role_lists_outside_registry():
    # Quoted role names in a row, or JS object keys with quoted values; prose such as MCP tool descriptions is not a list.
    gap = r'.{0,80}?'
    quoted = re.compile(gap.join(f"['\"]{role}['\"]" for role in ROLES))
    keyed = re.compile(gap.join(rf"\b{role}\s*:\s*['\"]" for role in ROLES))
    found = []
    for path in (ROOT / 'src/storygen').rglob('*'):
        if path.suffix not in {'.py', '.js', '.html'} or path.name in {'roles.py', 'roles.js'}:
            continue
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if quoted.search(line) or keyed.search(line):
                found.append(f'{path.relative_to(ROOT).as_posix()}:{number}')
    assert not found, found
