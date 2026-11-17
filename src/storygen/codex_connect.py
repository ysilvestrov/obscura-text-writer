"""STORE-MCP-001: preserve the user's Codex TOML; no processes or implicit profile reads."""
from __future__ import annotations

import os
import stat
import tempfile
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import tomlkit
from tomlkit.items import InlineTable

_LOCK = threading.Lock()
_HTTP_FIELDS = ('url', 'bearer_token_env_var', 'http_headers', 'env_http_headers', 'oauth',
                'http_headers_helper', 'oauth_resource', 'auth')


class CodexConfigError(ValueError):
    """Safe reason code, never the configuration's contents."""


@dataclass(frozen=True)
class ConfigResult:
    result: Literal['configured', 'unchanged']
    path: Path
    backup: Path | None
    created: bool


def config_path(userprofile: Path, codex_home: str | None) -> Path:
    home = Path(codex_home) if codex_home else userprofile/'.codex'
    if codex_home == '' or not home.is_absolute():
        raise CodexConfigError('config_home_must_be_absolute')
    return home/'config.toml'


def _document(content: bytes):
    try:
        doc = tomlkit.parse(content.decode('utf-8-sig'))
    except (ValueError, UnicodeError) as error:
        raise CodexConfigError('invalid_config') from None
    servers = doc.get('mcp_servers', {})
    if not isinstance(servers, Mapping):
        raise CodexConfigError('invalid_mcp_table')
    if 'obscura' in servers and not isinstance(servers['obscura'], Mapping):
        raise CodexConfigError('invalid_obscura_table')
    if "bearer_token" in servers.get("obscura", {}):
        raise CodexConfigError("deprecated_bearer_token")
    return doc


def _matches(doc, command: list[str]) -> bool:
    entry = doc.get('mcp_servers', {}).get('obscura', {})
    return (entry.get('command') == command[0] and entry.get('args', []) == command[1:]
            and entry.get('enabled', True) is True and not any(key in entry for key in _HTTP_FIELDS))


def _command(command: list[str]) -> None:
    if not command or any(not isinstance(arg, str) or not arg or '\0' in arg for arg in command):
        raise CodexConfigError('invalid_command')


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def config_status(path: Path, command: list[str]) -> dict[str, object]:
    _command(command)
    raw = _read(path)
    if raw is None:
        state = 'missing'
    else:
        try:
            state = 'configured' if _matches(_document(raw), command) else 'different'
        except CodexConfigError:
            state = 'invalid'
    return {'state': state, 'path': str(path)}


def _copy_permissions(source: Path, target: Path) -> None:
    """Keep private files private, including explicit Windows DACLs."""
    os.chmod(target, stat.S_IMODE(source.stat().st_mode))
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL('advapi32', use_last_error=True)
        get = api.GetFileSecurityW
        get.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
        get.restype = wintypes.BOOL
        size = wintypes.DWORD()
        get(str(source), 4, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        descriptor = ctypes.create_string_buffer(size.value)
        if not get(str(source), 4, descriptor, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        control = int.from_bytes(descriptor.raw[2:4], 'little')
        if not control & 0x0400:
            # Do not upgrade a legacy DACL: modern auto-inheritance would add parent ACEs.
            legacy = api.SetFileSecurityW
            legacy.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p)
            legacy.restype = wintypes.BOOL
            if not legacy(str(target), 4, descriptor):
                raise ctypes.WinError(ctypes.get_last_error())
            return
        get_dacl = api.GetSecurityDescriptorDacl
        get_dacl.argtypes = (ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL),
                            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL))
        get_dacl.restype = wintypes.BOOL
        present, defaulted = wintypes.BOOL(), wintypes.BOOL()
        dacl = ctypes.c_void_p()
        if not get_dacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)):
            raise ctypes.WinError(ctypes.get_last_error())
        set_security = api.SetNamedSecurityInfoW
        set_security.argtypes = (wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
                                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        set_security.restype = wintypes.DWORD
        protected = int.from_bytes(descriptor.raw[2:4], 'little') & 0x1000
        flags = 4 | (0x80000000 if protected else 0x20000000)
        status = set_security(str(target), 1, flags, None, None, dacl, None)
        if status:
            raise ctypes.WinError(status)


def write_config(path: Path, command: list[str]) -> ConfigResult:
    _command(command)
    path = Path(path)
    with _LOCK:
        raw = _read(path)
        doc = _document(raw or b'')
        if _matches(doc, command):
            return ConfigResult('unchanged', path, None, False)
        if 'mcp_servers' not in doc:
            doc['mcp_servers'] = tomlkit.table()
        servers = doc['mcp_servers']
        if 'obscura' not in servers:
            servers['obscura'] = tomlkit.inline_table() if isinstance(servers, InlineTable) else tomlkit.table()
        entry = servers['obscura']
        for key in _HTTP_FIELDS:
            entry.pop(key, None)
        entry['command'], entry['args'], entry['enabled'] = command[0], command[1:], True
        rendered = tomlkit.dumps(doc).encode('utf-8')
        if _document(rendered).unwrap() != doc.unwrap():
            raise CodexConfigError('invalid_serialized_config')
        path.parent.mkdir(parents=True, exist_ok=True)
        backup = None
        if raw is not None:
            backup = path.with_name(path.name + '.obscura-backup-' + uuid.uuid4().hex)
            # Exclusive creation prevents even an improbable UUID collision from overwriting a copy.
            with backup.open('xb'):
                pass
            _copy_permissions(path, backup)
            backup.write_bytes(raw)
        handle, name = tempfile.mkstemp(prefix='.obscura-', suffix='.tmp', dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(handle, 'wb') as stream:
                if raw is not None:
                    _copy_permissions(path, temporary)
                stream.write(rendered)
                stream.flush()
                os.fsync(stream.fileno())
            if _read(path) != raw:
                raise CodexConfigError('config_changed')
            os.replace(temporary, path)
            if path.read_bytes() != rendered:
                raise CodexConfigError('config_changed_after_write')
        finally:
            temporary.unlink(missing_ok=True)
        return ConfigResult('configured', path, backup, raw is None)


def powershell_command(command: list[str]) -> str:
    _command(command)
    return 'codex mcp add obscura -- ' + ' '.join("'" + arg.replace("'", "''") + "'" for arg in command)
