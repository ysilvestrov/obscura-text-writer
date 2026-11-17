"""STORE-MCP-001: Codex configuration is edited without touching the author's profile."""
import os
from pathlib import Path

import pytest
import tomlkit

from storygen import codex_connect as cc


COMMAND = [r'C:\Program Files\Obscura\obscura-mcp.exe', '--data-dir', r'C:\tmp\neutral library']


@pytest.mark.req('STORE-MCP-001')
def test_codex_roots_are_temporary(tmp_path_factory):
    base = tmp_path_factory.getbasetemp()
    assert Path(os.environ['USERPROFILE']).is_relative_to(base)
    assert os.environ['HOME'] == os.environ['USERPROFILE']
    assert Path.home() == Path(os.environ['USERPROFILE'])
    assert cc.config_path(Path.home(), os.environ['CODEX_HOME']).is_relative_to(base)


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


@pytest.mark.req('STORE-MCP-001')
def test_inline_parent_can_add_obscura_without_changing_other(tmp_path):
    path=tmp_path/'config.toml'
    path.write_text('mcp_servers = { other = { command = "other.exe" } }\n')
    assert cc.write_config(path,COMMAND).result == 'configured'
    doc=tomlkit.parse(path.read_text())
    assert doc['mcp_servers']['other']['command']=='other.exe'
    assert doc['mcp_servers']['obscura']['command']==COMMAND[0]
    assert cc.write_config(path,COMMAND).result=='unchanged'


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.parametrize('field,value', [
    ('http_headers_helper','helper'),
    ('oauth_resource','https://example.invalid/resource'),
    ('auth','oauth'),
])
def test_all_http_only_fields_are_removed_for_stdio(tmp_path,field,value):
    path=tmp_path/'config.toml'
    path.write_text('[mcp_servers.obscura]\nurl="https://example.invalid"\n'
                    'scopes=["read"]\n'+field+'="'+value+'"\n')
    assert cc.write_config(path,COMMAND).result=='configured'
    entry=tomlkit.parse(path.read_text())['mcp_servers']['obscura']
    assert field not in entry and entry['scopes']==['read']
    assert cc.config_status(path,COMMAND)['state']=='configured'


@pytest.mark.req('STORE-MCP-001')
def test_deprecated_bearer_token_is_refused_without_exposing_it(tmp_path):
    path=tmp_path/'config.toml'
    raw=b'[mcp_servers.obscura]\nurl="https://example.invalid"\nbearer_token="neutral-private"\n'
    path.write_bytes(raw)
    with pytest.raises(cc.CodexConfigError) as error:
        cc.write_config(path,COMMAND)
    assert 'neutral-private' not in str(error.value)
    assert path.read_bytes()==raw and cc.config_status(path,COMMAND)['state']=='invalid'
    assert list(tmp_path.iterdir())==[path]


@pytest.mark.req('STORE-MCP-001')
@pytest.mark.skipif(os.name!='nt',reason='Windows DACL API')
@pytest.mark.parametrize('mode',['legacy','inherited','protected'])
def test_private_acl_is_applied_before_bytes_and_preserved(tmp_path,monkeypatch,mode):
    import ctypes
    from ctypes import wintypes
    api=ctypes.WinDLL('advapi32',use_last_error=True)
    get=api.GetFileSecurityW
    get.argtypes=(wintypes.LPCWSTR,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD))
    get.restype=wintypes.BOOL
    def security(path):
        size=wintypes.DWORD()
        get(str(path),4,None,0,ctypes.byref(size))
        buffer=ctypes.create_string_buffer(size.value)
        assert get(str(path),4,buffer,size,ctypes.byref(size))
        return buffer
    def rights(path):
        descriptor=security(path)
        present,defaulted=wintypes.BOOL(),wintypes.BOOL()
        pointer=ctypes.c_void_p()
        getter=api.GetSecurityDescriptorDacl
        getter.argtypes=(ctypes.c_void_p,ctypes.POINTER(wintypes.BOOL),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.BOOL))
        getter.restype=wintypes.BOOL
        assert getter(descriptor,ctypes.byref(present),ctypes.byref(pointer),ctypes.byref(defaulted))
        size=int.from_bytes(ctypes.string_at(pointer,4)[2:4],'little') if pointer.value else 0
        # Windows may normalize AUTO_INHERITED cache bits. Compare actual ACEs and access/inheritance controls.
        control=int.from_bytes(descriptor.raw[2:4],'little') & 0x100C
        return control,ctypes.string_at(pointer,size) if size else b''
    path=tmp_path/'config.toml'
    path.write_text('model="neutral"\n')
    protected = mode == 'protected'
    if mode != 'legacy':
        buffer=security(path)
        present,defaulted=wintypes.BOOL(),wintypes.BOOL()
        dacl=ctypes.c_void_p()
        getter=api.GetSecurityDescriptorDacl
        getter.argtypes=(ctypes.c_void_p,ctypes.POINTER(wintypes.BOOL),ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.BOOL))
        getter.restype=wintypes.BOOL
        assert getter(buffer,ctypes.byref(present),ctypes.byref(dacl),ctypes.byref(defaulted))
        setter=api.SetNamedSecurityInfoW
        setter.argtypes=(wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p)
        setter.restype=wintypes.DWORD
        assert setter(str(path),1,4|(0x80000000 if protected else 0x20000000),None,None,dacl,None)==0
    expected=rights(path)
    assert bool(expected[0] & 0x1000)==protected
    fdopen=os.fdopen
    class CheckedWriter:
        def __init__(self,stream):
            self.stream=stream
        def __enter__(self):
            return self
        def __exit__(self,*args):
            self.stream.close()
        def __getattr__(self,name):
            return getattr(self.stream,name)
        def write(self,data):
            temporary=next(tmp_path.glob('.obscura-*.tmp'))
            assert rights(temporary)==expected, 'private bytes would be written before ACL'
            return self.stream.write(data)
    monkeypatch.setattr(os,'fdopen',lambda *a,**kw:CheckedWriter(fdopen(*a,**kw)))
    result=cc.write_config(path,COMMAND)
    assert rights(path)==expected
    assert rights(result.backup)==expected
