"""MODEL-001-S03: one role registry for the server and the browser."""
import ast
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
    for locale in ('uk', 'en'):
        for key in ROLE_LABEL_KEYS.values():
            assert isinstance(catalog[locale].get(key), str) and catalog[locale][key].strip(), (locale, key)


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


def python_role_lists(source):
    """Line numbers of literal tuples/lists/sets/dicts naming every role, in any order or layout."""
    lines = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            groups = [node.elts]
        elif isinstance(node, ast.Dict):
            # `{**STAGE_ROLE, 'classify': 'editor', ...}` extends a registry map with other stages; it is not a copy.
            if None in node.keys:
                continue
            groups = [node.keys, node.values]
        else:
            continue
        for group in groups:
            if ROLE_SET <= {item.value for item in group if isinstance(item, ast.Constant) and isinstance(item.value, str)}:
                lines.append(node.lineno)
    return lines


JS_GROUP = re.compile(r'\[[^\[\]]*\]|\{[^{}]*\}')
JS_STRING = re.compile(r"""['"]([A-Za-z_]+)['"]""")
JS_KEY = re.compile(r'(?:^|[{,\s])([A-Za-z_]+)\s*:')


def js_role_lists(source):
    """Line numbers of innermost [...] / {...} literals naming every role as strings or as object keys."""
    lines = []
    for match in JS_GROUP.finditer(source):
        body = match.group()
        if ROLE_SET <= set(JS_STRING.findall(body)) or ROLE_SET <= set(JS_KEY.findall(body)):
            lines.append(source.count('\n', 0, match.start()) + 1)
    return lines


def test_role_list_detector_ignores_order_and_layout():
    assert python_role_lists("X = ('writer', 'planner',\n     'memory', 'editor')\n") == [1]
    assert python_role_lists("X = {'brief': 'planner', 'draft': 'writer', 'edit': 'editor', 'memory': 'memory'}\n") == [1]
    assert python_role_lists('"""planner, writer, editor, memory"""\n') == []
    assert python_role_lists("X = {**STAGE_ROLE, 'a': 'planner', 'b': 'writer', 'c': 'editor', 'd': 'memory'}\n") == []
    assert js_role_lists("const a=[\n 'memory',\n 'writer','planner','editor'];") == [1]
    assert js_role_lists("const s={editor:'edit',planner:'brief',\nwriter:'draft',memory:'memory'};") == [1]
    assert js_role_lists("const l={get planner(){return t('a')},get writer(){return t('b')},get editor(){return t('c')},get memory(){return t('d')}};") == []


def test_no_inline_role_lists_outside_registry():
    found = []
    for path in (ROOT / 'src/storygen').rglob('*'):
        if path.suffix not in {'.py', '.js', '.html'} or path.name in {'roles.py', 'roles.js'}:
            continue
        source = path.read_text(encoding='utf-8')
        lines = python_role_lists(source) if path.suffix == '.py' else js_role_lists(source)
        found += [f'{path.relative_to(ROOT).as_posix()}:{line}' for line in lines]
    assert not found, found
