"""DESKTOP-001-S03: a verified copy of the data folder is made before a schema migration, or the app does not start."""
import json
import sqlite3
from datetime import datetime
from importlib.resources import files

import pytest

from storygen.storage import pre_migration
from storygen.storage.database import SCHEMA_VERSION
from storygen.storage.pre_migration import PreMigrationBackupFailed, backup_before_migration, backups_dir, pending_migration
from storygen.storage.repository import Repository

MIGRATIONS = ['001_initial', '002_trash', '003_publication', '004_authoring_comments']


def version(data):
    with sqlite3.connect(data / 'storygen.sqlite3') as db:
        return db.execute('PRAGMA user_version').fetchone()[0]


def old_schema_dir(tmp_path, upto=4, name='Мої твори'):
    data = tmp_path / name
    data.mkdir()
    db = sqlite3.connect(data / 'storygen.sqlite3')
    db.execute('PRAGMA journal_mode=WAL')
    for number, migration in enumerate(MIGRATIONS[:upto], 1):
        sql = files('storygen.storage').joinpath(f'migrations/{migration}.sql').read_text(encoding='utf-8')
        db.executescript('BEGIN IMMEDIATE;\n' + sql + f'\nPRAGMA user_version={number};\nCOMMIT;')
    db.close()
    (data / 'logs').mkdir()
    (data / 'logs' / 'obscura.log').write_text('рядок журналу\n', encoding='utf-8')
    return data


def test_schema_version_constant_matches_a_fresh_database(tmp_path):
    Repository(tmp_path / 'data')
    assert version(tmp_path / 'data') == SCHEMA_VERSION == 5


def test_no_database_and_current_schema_need_no_backup(tmp_path):
    empty = tmp_path / 'empty'
    assert pending_migration(empty) is None and backup_before_migration(empty) is None
    assert not empty.exists() and not backups_dir(empty).exists()
    Repository(tmp_path / 'data')
    assert pending_migration(tmp_path / 'data') is None and backup_before_migration(tmp_path / 'data') is None
    assert not backups_dir(tmp_path / 'data').exists()


def test_old_schema_is_backed_up_next_to_the_data_dir(tmp_path):
    data = old_schema_dir(tmp_path)
    assert pending_migration(data) == 4
    path = backup_before_migration(data, now=datetime(2026, 11, 11, 9, 30, 5))
    assert path == tmp_path / 'Мої твори-backups' / 'pre-migration-v4-20261111-093005'
    assert json.loads((path / 'manifest.json').read_text(encoding='utf-8'))['status'] == 'complete'
    assert version(path / 'data') == 4 and version(data) == 4
    assert (path / 'data' / 'logs' / 'obscura.log').read_text(encoding='utf-8') == 'рядок журналу\n'


def test_reading_the_version_does_not_change_the_data_dir(tmp_path):
    data = old_schema_dir(tmp_path)
    # SQLite may add its own -wal/-shm sidecar files when a WAL database is read; nothing else appears or changes.
    own = lambda: sorted(p.name for p in data.iterdir() if not p.name.endswith(('-wal', '-shm')))
    before, size = own(), (data / 'storygen.sqlite3').stat().st_size
    assert pending_migration(data) == 4
    assert own() == before and (data / 'storygen.sqlite3').stat().st_size == size and version(data) == 4


def test_backup_failure_blocks_the_migration(tmp_path, monkeypatch):
    data = old_schema_dir(tmp_path)

    def failing(source, destination):
        raise ValueError('Перевірка цілісності не пройдена: missing_file')
    monkeypatch.setattr(pre_migration, 'create_backup', failing)
    with pytest.raises(PreMigrationBackupFailed) as error:
        backup_before_migration(data)
    assert 'Резервну копію перед оновленням бази не створено' in str(error.value) and version(data) == 4


def test_existing_destination_is_a_failure_not_an_overwrite(tmp_path):
    data = old_schema_dir(tmp_path)
    moment = datetime(2026, 11, 11, 9, 30, 5)
    first = backup_before_migration(data, now=moment)
    with pytest.raises(PreMigrationBackupFailed):
        backup_before_migration(data, now=moment)
    assert json.loads((first / 'manifest.json').read_text(encoding='utf-8'))['status'] == 'complete'


def test_unwritable_backups_location_is_a_failure(tmp_path):
    data = old_schema_dir(tmp_path)
    backups_dir(data).write_text('не тека', encoding='utf-8')
    with pytest.raises(PreMigrationBackupFailed):
        backup_before_migration(data)
    assert version(data) == 4


def test_unreadable_version_is_a_failure_not_a_skipped_backup(tmp_path, monkeypatch):
    # A database that cannot be read right now (locked, damaged) must never be opened for migration without a copy.
    data = old_schema_dir(tmp_path)

    def locked(*args, **kwargs):
        raise sqlite3.OperationalError('database is locked')
    monkeypatch.setattr(pre_migration.sqlite3, 'connect', locked)
    with pytest.raises(PreMigrationBackupFailed):
        backup_before_migration(data)
    assert not backups_dir(data).exists()


def test_failed_copy_is_not_left_looking_like_a_backup(tmp_path, monkeypatch):
    data = old_schema_dir(tmp_path)
    real = pre_migration.create_backup

    def half(source, destination):
        destination.mkdir()
        (destination / 'manifest.json').write_text('{"status": "incomplete"}', encoding='utf-8')
        raise OSError(28, 'No space left on device')
    monkeypatch.setattr(pre_migration, 'create_backup', half)
    with pytest.raises(PreMigrationBackupFailed) as error:
        backup_before_migration(data, now=datetime(2026, 11, 11, 9, 30, 5))
    assert 'OSError' in str(error.value) and '28' in str(error.value)
    assert [p.name for p in backups_dir(data).iterdir()] == ['pre-migration-v4-20261111-093005.failed']
    monkeypatch.setattr(pre_migration, 'create_backup', real)
    assert backup_before_migration(data, now=datetime(2026, 11, 11, 9, 30, 5)).name == 'pre-migration-v4-20261111-093005'


def test_schema_one_cannot_be_verified_and_is_refused(tmp_path):
    # Known limitation: the verified backup knows schemas 2-5; a version 1 folder is refused, never migrated blindly.
    data = old_schema_dir(tmp_path, upto=1)
    with pytest.raises(PreMigrationBackupFailed) as error:
        backup_before_migration(data)
    assert 'unsupported_schema' in str(error.value) and version(data) == 1
