"""STORE-MCP-001: Codex configuration is edited without touching the author's profile."""
import os
from pathlib import Path

import pytest
import tomlkit

from storygen import codex_connect as cc


COMMAND = [r'C:\Program Files\Obscura\obscura-mcp.exe', '--data-dir', r'C:\tmp\neutral library']


@pytest.mark.req('STORE-MCP-001')
def test_codex_roots_are_temporary():
    assert Path(os.environ['USERPROFILE']).is_relative_to(Path('C:/tmp'))
    assert Path.home() == Path(os.environ['USERPROFILE'])
    assert cc.config_path(Path.home(), os.environ['CODEX_HOME']).is_relative_to(Path('C:/tmp'))


@pytest.mark.req('STORE-MCP-001')
def test_missing_config_is_created(tmp_path):
    path = tmp_path/'profile/config.toml'
    assert cc.config_status(path, COMMAND)['state'] == 'missing'
    result = cc.write_config(path, COMMAND)
    assert result.result == 'configured' and result.created and result.backup is None
    assert tomlkit.parse(path.read_text())['mcp_servers']['obscura'] == {
        'command': COMMAND[0], 'args': COMMAND[1:], 'enabled': True}
    assert cc.config_status(path, COMMAND)['state'] == 'configured'


@pytest.mark.req('STORE-MCP-001')
def test_existing_config_is_idempotent(tmp_path):
    path = tmp_path/'config.toml'
    cc.write_config(path, COMMAND)
    before = path.read_bytes()
    repeat = cc.write_config(path, COMMAND)
    assert repeat.result == 'unchanged' and not repeat.created and repeat.backup is None
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('*.obscura-backup*'))


@pytest.mark.req('STORE-MCP-001')
def test_http_migration_keeps_unrelated_settings(tmp_path):
    path = tmp_path/'config.toml'
    path.write_text('# authors comment\nmodel = "own"\n[mcp_servers.other]\ncommand = "other.exe"\n'
                    '[mcp_servers.obscura]\nurl = "http://old"\nenabled = false\n'
                    'http_headers = { Authorization = "private" }\n'
                    'enabled_tools = ["list_stories"]\n'
                    '[mcp_servers.obscura.env]\nCUSTOM = "kept"\n'
                    '[mcp_servers.obscura.oauth]\nclient_id = "old"\n', encoding='utf-8')
    assert cc.config_status(path, COMMAND)['state'] == 'different'
    result = cc.write_config(path, COMMAND)
    doc = tomlkit.parse(path.read_text())
    assert doc['model'] == 'own' and doc['mcp_servers']['other']['command'] == 'other.exe'
    assert path.read_text().startswith('# authors comment\n')
    entry = doc['mcp_servers']['obscura']
    assert entry['enabled'] is True and entry['command'] == COMMAND[0]
    assert entry['enabled_tools'] == ['list_stories'] and entry['env']['CUSTOM'] == 'kept'
    assert not ({'url', 'oauth', 'http_headers'} & set(entry))
    assert result.backup and 'private' in result.backup.read_text()
    assert 'private' not in str(cc.config_status(path, COMMAND))


@pytest.mark.parametrize('content', ['broken = [', 'mcp_servers = 1', '[mcp_servers]\nobscura = 1'])
@pytest.mark.req('STORE-MCP-001')
def test_invalid_toml_is_untouched(tmp_path, content):
    path = tmp_path/'config.toml'
    path.write_text(content)
    assert cc.config_status(path, COMMAND)['state'] == 'invalid'
    with pytest.raises(cc.CodexConfigError):
        cc.write_config(path, COMMAND)
    assert path.read_text() == content
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.req('STORE-MCP-001')
def test_non_table_is_untouched(tmp_path):
    path = tmp_path/'config.toml'
    path.write_text('mcp_servers = []')
    with pytest.raises(cc.CodexConfigError):
        cc.write_config(path, COMMAND)
    assert path.read_text() == 'mcp_servers = []'


@pytest.mark.req('STORE-MCP-001')
def test_unique_backup_keeps_exact_previous_bytes(tmp_path):
    path = tmp_path/'config.toml'
    original = b'# private\r\nmodel = "mine"\r\n'
    path.write_bytes(original)
    first = cc.write_config(path, COMMAND)
    assert first.backup.read_bytes() == original
    before = path.read_bytes()
    second = cc.write_config(path, [COMMAND[0], '--url', 'http://127.0.0.1:8766'])
    assert second.backup != first.backup and second.backup.read_bytes() == before
    assert first.backup.read_bytes() == original


@pytest.mark.req('STORE-MCP-001')
def test_changed_file_is_not_overwritten(tmp_path, monkeypatch):
    path = tmp_path/'config.toml'
    path.write_text('model = "before"\n')
    original_write = Path.write_bytes
    def concurrent(file, data):
        result = original_write(file, data)
        if '.obscura-backup' in file.name:
            original_write(path, b'model = "author"\n')
        return result
    monkeypatch.setattr(Path, 'write_bytes', concurrent)
    with pytest.raises(cc.CodexConfigError, match='changed'):
        cc.write_config(path, COMMAND)
    assert path.read_bytes() == b'model = "author"\n'


@pytest.mark.req('STORE-MCP-001')
def test_failed_replace_keeps_original(tmp_path, monkeypatch):
    path = tmp_path/'config.toml'
    path.write_text('model = "before"\n')
    def denied(*args):
        raise PermissionError('test')
    monkeypatch.setattr(os, 'replace', denied)
    with pytest.raises(PermissionError):
        cc.write_config(path, COMMAND)
    assert path.read_text() == 'model = "before"\n'


@pytest.mark.req('STORE-MCP-001')
def test_powershell_command_quotes_apostrophes():
    assert cc.powershell_command(["C:/O'Brien/bridge.exe", '--url', 'http://127.0.0.1:8765']) == (
        "codex mcp add obscura -- 'C:/O''Brien/bridge.exe' '--url' 'http://127.0.0.1:8765'")


@pytest.mark.parametrize('value', ['', 'relative', '../profile'])
@pytest.mark.req('STORE-MCP-001')
def test_config_home_must_be_absolute(tmp_path, value):
    with pytest.raises(cc.CodexConfigError):
        cc.config_path(tmp_path, value)


@pytest.mark.req('STORE-MCP-001')
def test_config_home_selects_explicit_profile(tmp_path):
    assert cc.config_path(tmp_path, None) == tmp_path/'.codex/config.toml'
    assert cc.config_path(tmp_path, str(tmp_path/'separate')) == tmp_path/'separate/config.toml'
