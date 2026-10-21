import json

from storygen.server import main
from storygen.storage.repository import Repository


def test_cli_fsck_without_server_or_environment(tmp_path, capsys, monkeypatch):
    Repository(tmp_path / 'data')
    def forbidden(*args, **kwargs):
        raise AssertionError('maintenance must not start the web app')
    monkeypatch.setattr('storygen.web.app.create_app', forbidden)
    assert main(['fsck', '--data-dir', str(tmp_path / 'data'), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['ok'] is True


def test_cli_missing_database_has_nonzero_status(tmp_path, capsys):
    assert main(['fsck', '--data-dir', str(tmp_path / 'missing'), '--json']) == 1
    assert json.loads(capsys.readouterr().out)['ok'] is False
    assert not (tmp_path / 'missing').exists()


def test_cli_backup_and_restore(tmp_path, capsys):
    Repository(tmp_path / 'source')
    assert main(['backup', '--data-dir', str(tmp_path / 'source'), '--destination', str(tmp_path / 'backup'), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['ok']
    assert main(['restore', '--backup-dir', str(tmp_path / 'backup'), '--destination', str(tmp_path / 'copy'), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['ok']
