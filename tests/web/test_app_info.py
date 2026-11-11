import pytest
from fastapi.testclient import TestClient

from storygen import build_edition
from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def client(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    return TestClient(app, base_url='http://127.0.0.1')


def test_app_info_full_edition(tmp_path):
    info = client(tmp_path).get('/api/app-info').json()
    assert info['edition'] == 'full' and info['max_rating'] == {'sexual': 2, 'violence': 2, 'themes': 2}
    assert set(info) == {'edition', 'max_rating', 'version', 'support_url', 'waitlist_url', 'report_url'}
    assert info['support_url'] == info['waitlist_url'] == info['report_url'] == ''
    assert isinstance(info['version'], str) and info['version']


def test_app_info_store_edition(tmp_path, store_edition):
    info = client(tmp_path).get('/api/app-info').json()
    assert info['edition'] == 'store' and info['max_rating'] == {'sexual': 1, 'violence': 2, 'themes': 2}
    assert info['report_url'] == 'https://example.test/report'


def test_app_does_not_start_with_invalid_marker(tmp_path, monkeypatch):
    def broken():
        raise ValueError('Некоректний файл видання build_edition.json: видання для Store потребує report_url')
    monkeypatch.setattr(build_edition, 'current', broken)
    with pytest.raises(ValueError, match='report_url'):
        create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    assert not (tmp_path / 'data').exists()
