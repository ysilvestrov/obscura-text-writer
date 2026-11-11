import pytest

from storygen.providers import secrets
from storygen.providers.secrets import (SecretStoreUnavailable, delete_key, key_source, resolve_key, set_backend, store_key,
    stored, valid_name)


def test_environment_wins_over_store(monkeypatch, secret_store):
    secret_store.set('OPENROUTER_API_KEY', 'from-store')
    assert (resolve_key('OPENROUTER_API_KEY'), key_source('OPENROUTER_API_KEY')) == ('from-store', 'store')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'from-env')
    assert (resolve_key('OPENROUTER_API_KEY'), key_source('OPENROUTER_API_KEY')) == ('from-env', 'env')
    assert stored('OPENROUTER_API_KEY') is True


def test_missing_everywhere(secret_store, monkeypatch):
    monkeypatch.delenv('VENICE_API_KEY', raising=False)
    assert resolve_key('VENICE_API_KEY') is None and key_source('VENICE_API_KEY') is None and resolve_key(None) is None
    assert stored('VENICE_API_KEY') is False


def test_empty_environment_value_counts_as_missing(secret_store, monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY', '')
    secret_store.set('VENICE_API_KEY', 'from-store')
    assert (resolve_key('VENICE_API_KEY'), key_source('VENICE_API_KEY')) == ('from-store', 'store')


def test_store_and_delete_roundtrip(secret_store):
    store_key('VENICE_API_KEY', '  secret-value\n')
    assert secret_store.get('VENICE_API_KEY') == 'secret-value'
    delete_key('VENICE_API_KEY')
    delete_key('VENICE_API_KEY')
    assert stored('VENICE_API_KEY') is False


@pytest.mark.parametrize('name', ['path', 'A', 'lower_case_KEY', 'WITH-DASH', 'X' * 65, '', '../X', 'КЛЮЧ_API'])
def test_invalid_names_are_rejected_for_writes(secret_store, name):
    assert valid_name(name) is False
    with pytest.raises(ValueError, match='Некоректна назва ключа'):
        store_key(name, 'v')
    with pytest.raises(ValueError, match='Некоректна назва ключа'):
        delete_key(name)
    assert secret_store.items == {}


def test_valid_names():
    assert all(valid_name(name) for name in ['OPENROUTER_API_KEY', 'VENICE_API_KEY', 'MY_KEY_2', 'ABC'])


def test_blank_value_is_rejected(secret_store):
    with pytest.raises(ValueError, match='Ключ не може бути порожнім'):
        store_key('VENICE_API_KEY', ' \n')
    assert secret_store.items == {}


def test_unavailable_store_reads_as_missing_and_refuses_writes(monkeypatch):
    monkeypatch.delenv('VENICE_API_KEY', raising=False)
    set_backend(None)
    assert secrets.store_available() is False
    assert resolve_key('VENICE_API_KEY') is None and stored('VENICE_API_KEY') is False
    with pytest.raises(SecretStoreUnavailable):
        store_key('VENICE_API_KEY', 'v')
    with pytest.raises(SecretStoreUnavailable):
        delete_key('VENICE_API_KEY')
    monkeypatch.setenv('VENICE_API_KEY', 'from-env')
    assert resolve_key('VENICE_API_KEY') == 'from-env'


def test_store_that_raises_on_read_is_treated_as_missing(secret_store, monkeypatch):
    monkeypatch.delenv('VENICE_API_KEY', raising=False)

    def boom(name):
        raise RuntimeError('locked profile')
    monkeypatch.setattr(secret_store, 'get', boom)
    assert resolve_key('VENICE_API_KEY') is None and key_source('VENICE_API_KEY') is None and stored('VENICE_API_KEY') is False


def test_store_that_raises_on_write_reports_unavailable(secret_store, monkeypatch):
    def boom(name, value):
        raise RuntimeError('secret-value must not leak')
    monkeypatch.setattr(secret_store, 'set', boom)
    with pytest.raises(SecretStoreUnavailable) as error:
        store_key('VENICE_API_KEY', 'secret-value')
    assert 'secret-value' not in str(error.value)


def test_real_keyring_adapter_with_memory_keyring():
    keyring = pytest.importorskip('keyring')
    from keyring.backend import KeyringBackend
    from keyring.errors import PasswordDeleteError

    class Memory(KeyringBackend):
        priority = 1

        def __init__(self):
            super().__init__()
            self.items = {}

        def get_password(self, service, username):
            return self.items.get((service, username))

        def set_password(self, service, username, password):
            self.items[(service, username)] = password

        def delete_password(self, service, username):
            if (service, username) not in self.items:
                raise PasswordDeleteError('absent')
            del self.items[(service, username)]

    previous = keyring.get_keyring()
    memory = Memory()
    keyring.set_keyring(memory)
    try:
        set_backend(secrets.default_backend())
        assert secrets.store_available() is True
        store_key('VENICE_API_KEY', 'value-1')
        assert memory.items == {('Obscura', 'VENICE_API_KEY'): 'value-1'}
        assert stored('VENICE_API_KEY') is True
        delete_key('VENICE_API_KEY')
        delete_key('VENICE_API_KEY')
        assert memory.items == {}
    finally:
        keyring.set_keyring(previous)


def test_default_backend_is_unavailable_with_the_fail_keyring():
    keyring = pytest.importorskip('keyring')
    from keyring.backends.fail import Keyring as Fail
    previous = keyring.get_keyring()
    keyring.set_keyring(Fail())
    try:
        assert secrets.default_backend() is None
    finally:
        keyring.set_keyring(previous)
