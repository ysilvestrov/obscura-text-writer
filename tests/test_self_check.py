"""PACKAGING-001-S01: the built application checks itself and the build script believes only this report."""
import json
import ssl

import pytest

from storygen import desktop, self_check
from storygen.self_check import run_checks

NAMES = ['tls_context', 'edition_marker', 'package_data', 'key_store', 'tray', 'database', 'licenses']


def by_name(report):
    return {check['name']: check for check in report['checks']}


def test_checks_pass_in_the_development_environment():
    pytest.importorskip('pystray')
    pytest.importorskip('keyring')
    report = run_checks()
    assert [check['name'] for check in report['checks']] == NAMES
    assert report['ok'] is True, [c for c in report['checks'] if not c['ok']]
    assert report['frozen'] is False and report['edition'] == 'full'
    assert report['max_rating'] == {'sexual': 2, 'violence': 2, 'themes': 2}
    assert isinstance(report['version'], str) and report['version']
    assert by_name(report)['licenses']['detail'] == 'не заморожена збірка'


def test_broken_tls_is_reported_not_raised(monkeypatch):
    def broken(*args, **kwargs):
        raise FileNotFoundError(2, 'No such file or directory')
    monkeypatch.setattr(ssl, 'create_default_context', broken)
    report = run_checks()
    check = by_name(report)['tls_context']
    assert report['ok'] is False and check == {'name': 'tls_context', 'ok': False, 'detail': 'FileNotFoundError'}
    assert [c['name'] for c in report['checks']] == NAMES          # the other checks still ran


def test_missing_package_data_names_the_missing_file(monkeypatch):
    monkeypatch.setattr(self_check, 'REQUIRED_FILES', [('storygen.web', 'static/i18n.json'), ('storygen.web', 'static/absent-file.bin')])
    check = by_name(run_checks())['package_data']
    assert check['ok'] is False and check['detail'] == 'storygen.web/static/absent-file.bin'


def test_store_edition_is_reported(store_edition):
    report = run_checks()
    assert report['edition'] == 'store' and report['max_rating']['sexual'] == 1
    assert by_name(report)['edition_marker']['ok'] is True


def test_invalid_edition_marker_fails_the_check(monkeypatch):
    from storygen import build_edition

    def broken():
        raise ValueError('Некоректний файл видання build_edition.json: невідоме видання або зайві поля')
    monkeypatch.setattr(build_edition, 'current', broken)
    report = run_checks()
    assert report['ok'] is False and report['edition'] is None and by_name(report)['edition_marker']['ok'] is False


def test_key_store_check_never_reads_or_writes_the_store(monkeypatch):
    keyring = pytest.importorskip('keyring')

    def touched(*args, **kwargs):
        raise AssertionError('the self-check must not touch credentials')
    for name in ('get_password', 'set_password', 'delete_password'):
        monkeypatch.setattr(keyring, name, touched)
    assert by_name(run_checks())['key_store']['ok'] is True


def test_missing_key_store_fails_the_check(monkeypatch):
    from storygen.providers import secrets
    monkeypatch.setattr(secrets, 'default_backend', lambda: None)
    assert by_name(run_checks())['key_store']['ok'] is False


def test_frozen_build_needs_the_notices_file(monkeypatch, tmp_path):
    monkeypatch.setattr(self_check.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(self_check.sys, 'executable', str(tmp_path / 'Obscura.exe'))
    assert by_name(run_checks())['licenses']['ok'] is False
    (tmp_path / 'THIRD-PARTY-NOTICES.txt').write_text('notices', encoding='utf-8')
    report = run_checks()
    assert by_name(report)['licenses']['ok'] is True and report['frozen'] is True


def test_details_never_carry_the_user_profile_path(monkeypatch, tmp_path):
    def broken(*args, **kwargs):
        raise OSError(2, 'No such file', str(tmp_path / 'Користувач' / 'secret.pem'))
    monkeypatch.setattr(ssl, 'create_default_context', broken)
    assert 'Користувач' not in json.dumps(run_checks(), ensure_ascii=False)


def test_self_check_mode_writes_the_report_and_starts_nothing(tmp_path):
    pytest.importorskip('pystray')
    pytest.importorskip('keyring')

    def never(*args, **kwargs):
        raise AssertionError('the self-check must not start the application')
    report_path = tmp_path / 'report.json'
    code = desktop.main(['--self-check', str(report_path), '--data-dir', str(tmp_path / 'data')], opener=never, tray=never, serve=never, alert=never)
    report = json.loads(report_path.read_text(encoding='utf-8'))
    assert code == 0 and report['ok'] is True and not (tmp_path / 'data').exists()


def test_self_check_mode_returns_5_when_a_check_fails(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise FileNotFoundError(2, 'No such file or directory')
    monkeypatch.setattr(ssl, 'create_default_context', broken)
    report_path = tmp_path / 'report.json'
    assert desktop.main(['--self-check', str(report_path)], alert=lambda text: None) == 5
    assert json.loads(report_path.read_text(encoding='utf-8'))['ok'] is False


def test_frozen_package_data_is_checked_file_by_file_against_the_build_manifest(monkeypatch):
    # PACKAGING-001: data files must be the ones of the checkout that was built, not of some installed copy.
    import hashlib
    from importlib.resources import files
    from storygen import build_manifest
    real = files('storygen').joinpath('web/static/i18n.json').read_bytes()
    good = {'version': '9.9.9', 'files': {'web/static/i18n.json': hashlib.sha256(real).hexdigest()}}
    monkeypatch.setattr(build_manifest, 'load', lambda: good)
    report = run_checks()
    assert by_name(report)['package_data'] == {'name': 'package_data', 'ok': True, 'detail': '1 файлів за маніфестом збірки'}
    assert report['version'] == '9.9.9'
    monkeypatch.setattr(build_manifest, 'load', lambda: {'version': '9.9.9', 'files': {'web/static/i18n.json': '0' * 64}})
    assert by_name(run_checks())['package_data']['detail'] == 'файл відрізняється від робочої копії: web/static/i18n.json'
    monkeypatch.setattr(build_manifest, 'load', lambda: {'version': '9.9.9', 'files': {'web/templates/absent.html': '0' * 64}})
    assert by_name(run_checks())['package_data']['detail'] == 'немає файла web/templates/absent.html'


def test_foreign_lookup_errors_do_not_leak_their_text(monkeypatch, tmp_path):
    # A KeyError from third-party code may carry a path as its key; only this module's own failures are echoed.
    from storygen import build_edition

    def broken():
        raise KeyError(str(tmp_path / 'Користувач' / 'secret'))
    monkeypatch.setattr(build_edition, 'current', broken)
    report = run_checks()
    assert by_name(report)['edition_marker'] == {'name': 'edition_marker', 'ok': False, 'detail': 'KeyError'}
    assert 'Користувач' not in json.dumps(report, ensure_ascii=False)


def test_app_info_reports_the_version_of_the_build_manifest(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from storygen import build_manifest
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    monkeypatch.setattr(build_manifest, 'load', lambda: {'version': '3.2.1', 'files': {}})
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    assert TestClient(app, base_url='http://127.0.0.1').get('/api/app-info').json()['version'] == '3.2.1'
