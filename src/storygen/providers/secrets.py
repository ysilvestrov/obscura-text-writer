"""Where a provider key comes from: an environment variable first, then the OS credential store (SECURITY-002).

The value of a key leaves this module only towards the provider client and the redaction of error texts; it is never
returned to the interface, logged or written into the data directory.
"""
import os
import re
from typing import Literal

SERVICE = 'Obscura'
_NAME = re.compile(r'[A-Z][A-Z0-9_]{2,63}')
_UNSET = object()
_backend = _UNSET
# A Windows credential blob holds 2560 bytes (1280 UTF-16 characters); real provider keys are far shorter.
MAX_VALUE = 1024


class SecretStoreUnavailable(ValueError):
    def __init__(self):
        super().__init__('Сховище ключів недоступне на цьому комп’ютері. Задайте ключ змінною середовища.')


class _KeyringBackend:
    """The `keyring` library: Windows Credential Manager, macOS Keychain, Secret Service."""

    def __init__(self, keyring):
        self._keyring = keyring

    def get(self, name):
        return self._keyring.get_password(SERVICE, name)

    def set(self, name, value):
        self._keyring.set_password(SERVICE, name, value)

    def delete(self, name):
        from keyring.errors import PasswordDeleteError
        try:
            self._keyring.delete_password(SERVICE, name)
        except PasswordDeleteError:
            pass  # Already absent: deleting is idempotent.


def default_backend():
    """The OS store, or None when the optional `keyring` package or a usable backend is missing."""
    try:
        import keyring
        from keyring.backends.fail import Keyring as Fail
        if isinstance(keyring.get_keyring(), Fail):
            return None
        return _KeyringBackend(keyring)
    except Exception:
        return None


def set_backend(backend) -> None:
    """Replace the store (tests, or None for "no store"); objects need get(name), set(name, value), delete(name)."""
    global _backend
    _backend = backend


def _store():
    global _backend
    if _backend is _UNSET:
        _backend = default_backend()
    return _backend


def store_available() -> bool:
    return _store() is not None


def store_state(name) -> tuple[bool, bool]:
    """(a key for this name is stored, the store answered): a store that fails on reading is not available."""
    store = _store()
    if store is None or not valid_name(name):
        return False, store is not None
    try:
        return bool(store.get(name)), True
    except Exception:
        return False, False


def _environment(name):
    # An empty or whitespace-only variable is not a key.
    return (os.environ.get(name) or '').strip() or None


def valid_name(name) -> bool:
    return isinstance(name, str) and _NAME.fullmatch(name) is not None


def _from_store(name):
    # Only names this module could have written are looked up; any store failure reads as "no key".
    store = _store()
    if store is None or not valid_name(name):
        return None
    try:
        return store.get(name) or None
    except Exception:
        return None


def resolve_key(name) -> str | None:
    if not name:
        return None
    return _environment(name) or _from_store(name)


def key_source(name) -> Literal['env', 'store'] | None:
    if name and _environment(name):
        return 'env'
    return 'store' if _from_store(name) else None


def stored(name) -> bool:
    return _from_store(name) is not None


def _writable(name):
    if not valid_name(name):
        raise ValueError('Некоректна назва ключа')
    store = _store()
    if store is None:
        raise SecretStoreUnavailable()
    return store


def store_key(name, value: str) -> None:
    store = _writable(name)
    value = value.strip() if isinstance(value, str) else ''
    if not value:
        raise ValueError('Ключ не може бути порожнім')
    if len(value) > MAX_VALUE:
        raise ValueError('Ключ задовгий')
    try:
        store.set(name, value)
    except Exception:
        # The original error may quote the value.
        raise SecretStoreUnavailable() from None


def delete_key(name) -> None:
    store = _writable(name)
    try:
        store.delete(name)
    except Exception:
        raise SecretStoreUnavailable() from None
