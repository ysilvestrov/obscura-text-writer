"""DESKTOP-001-S03: a verified copy of the data folder before a schema migration of the installed build."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .backup import create_backup
from .database import SCHEMA_VERSION

DATABASE = 'storygen.sqlite3'


class PreMigrationBackupFailed(ValueError):
    """Author-facing: the reason is a code-owned backup diagnostic, never story text."""

    def __init__(self, reason: str):
        super().__init__('Резервну копію перед оновленням бази не створено, тому базу не змінено: ' + reason)


def backups_dir(data_dir: Path) -> Path:
    # Next to the data folder, never inside it: the verified backup refuses a nested destination (MAINT-002).
    data_dir = Path(data_dir)
    return data_dir.parent / (data_dir.name + '-backups')


def pending_migration(data_dir: Path) -> int | None:
    """The schema version of an existing database that a start would migrate; None when there is nothing to migrate.

    Opens the database read-only; SQLite may still add its -wal/-shm sidecar files next to a WAL database.
    Raises sqlite3.Error when the version cannot be read: an unreadable database is never "nothing to migrate"."""
    path = Path(data_dir) / DATABASE
    if not path.is_file():
        return None
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
    return version if 0 < version < SCHEMA_VERSION else None


def _reason(error: Exception) -> str:
    if isinstance(error, OSError):
        return f'{type(error).__name__} [{error.errno}]'  # no path: it may name a story file
    if isinstance(error, sqlite3.Error):
        return f'базу не вдалося прочитати ({type(error).__name__})'
    return str(error)


def backup_before_migration(data_dir: Path, now: datetime | None = None) -> Path | None:
    data_dir = Path(data_dir)
    try:
        version = pending_migration(data_dir)
    except sqlite3.Error as error:
        raise PreMigrationBackupFailed(_reason(error)) from None
    if version is None:
        return None
    stamp = (now or datetime.now()).strftime('%Y%m%d-%H%M%S')
    destination = backups_dir(data_dir) / f'pre-migration-v{version}-{stamp}'
    existed = destination.exists()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        return create_backup(data_dir, destination)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        # A half-made copy must not sit there under the name of a complete one.
        if not existed and destination.exists():
            try:
                destination.rename(destination.with_name(destination.name + '.failed'))
            except OSError:
                pass
        raise PreMigrationBackupFailed(_reason(error)) from None
