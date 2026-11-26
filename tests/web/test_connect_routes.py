"""STORE-MCP-001 S08–S11: the connect routes of the library block; the bridge may never use them."""
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from storygen import claude_connect as cc
from storygen.application.settings import AppSettings
from storygen.web import routes_connect
from storygen.web.app import create_app

BASE = 'http://127.0.0.1:8765'


@pytest.fixture
def roots(tmp_path, monkeypatch):
    made = cc.Roots(local_appdata=tmp_path / 'Local', appdata=tmp_path / 'Roaming', userprofile=tmp_path / 'home')
    for folder in (made.local_appdata, made.appdata, made.userprofile):
        folder.mkdir()
    monkeypatch.setattr(routes_connect, '_roots', lambda: made)
    monkeypatch.setattr(routes_connect, '_open_folder', lambda path: None)
    return made


@pytest.fixture
def client(tmp_path, roots):
    with TestClient(create_app(AppSettings(data_dir=tmp_path / 'data')), base_url=BASE) as made:
        yield made


def store_config(roots, content='{"mcpServers": {}}'):
    (roots.local_appdata / 'Packages' / 'Claude_abc123').mkdir(parents=True)
    config = roots.local_appdata / 'Claude-Data' / 'claude_abc123' / 'claude_desktop_config.json'
    config.parent.mkdir(parents=True)
    config.write_text(content, encoding='utf-8')
    return config


@pytest.mark.req('STORE-MCP-001')
def test_desktop_entry_is_written_and_reported_with_its_file(client, roots):
    config = store_config(roots)
    answer = client.post('/api/connect/claude-desktop')
    assert answer.status_code == 200 and answer.json()['result'] == 'added' and answer.json()['path'] == str(config)
    entry = json.loads(config.read_text(encoding='utf-8'))['mcpServers']['obscura']
    assert entry['command'].endswith('storygen-mcp.exe') and entry['args'][0] == '--url'
    status = client.get('/api/connect/status').json()
    assert status['desktop'] == {'path': str(config), 'variant': 'store', 'has_entry': True}
    assert 'connected' not in json.dumps(answer.json()).lower()


@pytest.mark.req('STORE-MCP-001')
def test_missing_config_offers_the_fallback(client, roots):
    answer = client.post('/api/connect/claude-desktop')
    assert answer.status_code == 404 and answer.json()['fallback'] is True
    assert 'запустіть Claude Desktop хоч раз' in answer.json()['detail']
    assert client.get('/api/connect/status').json()['desktop'] is None


@pytest.mark.req('STORE-MCP-001')
def test_unusable_config_names_the_file(client, roots):
    config = store_config(roots, '{"mcpServers": [')
    answer = client.post('/api/connect/claude-desktop')
    assert answer.status_code == 422 and answer.json()['path'] == str(config) and answer.json()['fallback'] is True
    assert config.read_text(encoding='utf-8') == '{"mcpServers": ['


@pytest.mark.req('STORE-MCP-001')
def test_bundle_is_built_in_the_data_folder(client, roots, tmp_path, monkeypatch):
    launcher = tmp_path / 'storygen-mcp.exe'
    launcher.write_bytes(b'MZ')
    monkeypatch.setattr(routes_connect, '_launcher', lambda command: launcher)
    opened = []
    monkeypatch.setattr(routes_connect, '_open_folder', opened.append)
    answer = client.post('/api/connect/claude-desktop/bundle')
    bundle = tmp_path / 'data' / 'claude' / 'obscura.mcpb'
    assert answer.status_code == 200 and answer.json()['path'] == str(bundle) and opened == [bundle.parent]
    with zipfile.ZipFile(bundle) as archive:
        assert json.loads(archive.read('manifest.json'))['server']['mcp_config']['command'].endswith('storygen-mcp.exe')


@pytest.mark.req('STORE-MCP-001')
def test_claude_code_connected_or_command_to_copy(client, roots, monkeypatch):
    monkeypatch.setattr(cc, 'find_claude_code', lambda found_roots: None)
    missing = client.post('/api/connect/claude-code')
    assert missing.status_code == 404 and missing.json()['command'].startswith('claude mcp add --scope user obscura -- ')
    calls = []
    monkeypatch.setattr(cc, 'find_claude_code', lambda found_roots: roots.userprofile / 'claude.exe')
    monkeypatch.setattr(cc, 'connect_claude_code', lambda claude, command: calls.append(command) or True)
    monkeypatch.setattr(cc, 'connect_claude_plugin', lambda claude, target: True)
    answer = client.post('/api/connect/claude-code')
    assert answer.status_code == 200 and answer.json()['connected'] is True and calls[0][0].endswith('storygen-mcp.exe')


@pytest.mark.req('STORE-MCP-001')
def test_code_route_reports_mcp_and_skills(client, roots, monkeypatch, tmp_path):
    plugin_calls = []
    monkeypatch.setattr(cc, 'find_claude_code', lambda found_roots: roots.userprofile / 'claude.exe')
    monkeypatch.setattr(cc, 'connect_claude_code', lambda claude, command: True)
    monkeypatch.setattr(cc, 'connect_claude_plugin', lambda claude, target: plugin_calls.append(target) or True)
    answer = client.post('/api/connect/claude-code')
    target = tmp_path / 'data' / 'claude' / 'marketplace'
    body = answer.json()
    assert answer.status_code == 200 and {'found', 'connected', 'skills', 'command', 'plugin_commands'} <= set(body)
    assert body['skills'] is True and plugin_calls == [target]
    assert (target / cc.VERSION_MARKER).is_file() and (target / 'obscura' / 'skills' / 'publish' / 'SKILL.md').is_file()
    assert body['plugin_commands'] == cc.plugin_commands(target)


@pytest.mark.req('STORE-MCP-001')
def test_code_route_conflict(client, roots, monkeypatch, tmp_path):
    target = tmp_path / 'data' / 'claude' / 'marketplace'
    target.mkdir(parents=True)
    (target / 'notes.txt').write_text('mine', encoding='utf-8')
    monkeypatch.setattr(cc, 'find_claude_code', lambda found_roots: roots.userprofile / 'claude.exe')
    monkeypatch.setattr(cc, 'connect_claude_code', lambda claude, command: True)
    monkeypatch.setattr(cc, 'connect_claude_plugin', lambda claude, target: pytest.fail('plugin over a foreign folder'))
    body = client.post('/api/connect/claude-code').json()
    assert body['connected'] is True and body['skills'] is False and body['conflict'] == str(target)
    assert sorted(p.name for p in target.iterdir()) == ['notes.txt']


@pytest.mark.req('STORE-MCP-001')
def test_code_route_without_plugin(client, roots, monkeypatch):
    monkeypatch.setattr(routes_connect, '_marketplace_source', lambda: None)
    monkeypatch.setattr(cc, 'find_claude_code', lambda found_roots: roots.userprofile / 'claude.exe')
    monkeypatch.setattr(cc, 'connect_claude_code', lambda claude, command: True)
    monkeypatch.setattr(cc, 'connect_claude_plugin', lambda claude, target: pytest.fail('no plugin to install'))
    body = client.post('/api/connect/claude-code').json()
    assert body['connected'] is True and body['skills'] is False and body['reason'] == 'no_plugin'


@pytest.mark.req('STORE-MCP-001')
def test_restart_runs_only_the_fixed_action(client, roots, monkeypatch):
    config = store_config(roots)
    seen = []
    monkeypatch.setattr(cc, 'restart_desktop', lambda found, found_roots: seen.append(found) or True)
    answer = client.post('/api/connect/claude-desktop/restart', json={'argv': ['calc.exe']})
    assert answer.status_code == 200 and answer.json() == {'started': True}
    assert seen == [cc.DesktopConfig(config, 'store', 'Claude_abc123')]


@pytest.mark.req('STORE-MCP-001')
def test_missing_launcher_refuses_the_bundle(client, roots, tmp_path, monkeypatch):
    monkeypatch.setattr(routes_connect, '_launcher', lambda command: tmp_path / 'absent.exe')
    answer = client.post('/api/connect/claude-desktop/bundle')
    assert answer.status_code == 409 and answer.json()['detail_original'] == routes_connect.NO_LAUNCHER
    assert not (tmp_path / 'data' / 'claude' / 'obscura.mcpb').exists()


@pytest.mark.req('STORE-MCP-001')
def test_restart_without_config_does_nothing(client, roots, monkeypatch):
    monkeypatch.setattr(cc, 'restart_desktop', lambda *args: pytest.fail('restart without a config'))
    answer = client.post('/api/connect/claude-desktop/restart')
    assert answer.status_code == 404 and answer.json()['detail_original'] == routes_connect.NO_DESKTOP_CONFIG


@pytest.mark.req('STORE-MCP-001')
def test_claude_code_unconfirmed_keeps_the_command(client, roots, monkeypatch):
    monkeypatch.setattr(cc, 'find_claude_code', lambda found_roots: roots.userprofile / 'claude.exe')
    monkeypatch.setattr(cc, 'connect_claude_code', lambda claude, command: False)
    monkeypatch.setattr(cc, 'connect_claude_plugin', lambda claude, target: False)
    answer = client.post('/api/connect/claude-code')
    assert answer.status_code == 200 and answer.json()['connected'] is False
    assert answer.json()['command'].startswith('claude mcp add --scope user obscura -- ')


@pytest.mark.req('STORE-MCP-001')
def test_desktop_skills_route(client, roots, monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(routes_connect, '_open_folder', opened.append)
    answer = client.post('/api/connect/claude-desktop/skills')
    folder = tmp_path / 'data' / 'claude' / 'skills'
    body = answer.json()
    assert answer.status_code == 200 and body['folder'] == str(folder) and opened == [folder]
    assert len(body['files']) == 6 and all((folder / name).is_file() for name in body['files'])


@pytest.mark.req('STORE-MCP-001')
def test_desktop_skills_without_plugin(client, roots, monkeypatch, tmp_path):
    monkeypatch.setattr(routes_connect, '_marketplace_source', lambda: None)
    answer = client.post('/api/connect/claude-desktop/skills')
    assert answer.status_code == 409 and answer.json()['detail_original'] == routes_connect.NO_PLUGIN
    assert not (tmp_path / 'data' / 'claude' / 'skills').exists()


@pytest.mark.req('STORE-MCP-001')
def test_desktop_skills_write_failure_is_a_refusal(client, roots, monkeypatch):
    def failing(plugin, folder):
        raise OSError('disk full')
    monkeypatch.setattr(cc, 'write_desktop_skills', failing)
    answer = client.post('/api/connect/claude-desktop/skills')
    assert answer.status_code == 500 and answer.json()['detail_original'] == routes_connect.SKILLS_WRITE_FAILED


@pytest.mark.req('STORE-MCP-001')
def test_bridge_cannot_use_connect_routes(client, roots, monkeypatch):
    store_config(roots)
    touched = []
    for name in ('write_desktop_entry', 'build_mcpb', 'connect_claude_code', 'restart_desktop', 'sync_marketplace',
                 'connect_claude_plugin', 'write_desktop_skills'):
        monkeypatch.setattr(cc, name, lambda *args, _name=name, **kwargs: touched.append(_name))
    for path in ('claude-desktop', 'claude-desktop/bundle', 'claude-code', 'claude-desktop/restart', 'claude-desktop/skills'):
        answer = client.post(f'/api/connect/{path}', headers={'X-Obscura-Client': 'mcp'})
        assert answer.status_code == 403 and 'лише автор' in answer.json()['detail']
    assert touched == []


@pytest.mark.req('STORE-MCP-001')
def test_foreign_origin_is_refused(client, roots):
    store_config(roots)
    answer = client.post('/api/connect/claude-desktop', headers={'Origin': 'https://evil.example'})
    assert answer.status_code == 403


@pytest.mark.req('STORE-MCP-001')
def test_web_tests_never_reach_the_real_claude(tmp_path):
    # tests/conftest.py: any test that reaches a connect route works in temporary folders, finds no Claude Code
    # and opens no Explorer window, so the author's Claude settings are never written by the suite.
    assert tmp_path.parent in routes_connect._roots().local_appdata.parents
    assert cc.find_claude_code(routes_connect._roots()) is None
    assert routes_connect._open_folder(tmp_path) is None
