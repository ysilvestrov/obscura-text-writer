"""PACKAGING-001-S01: what a built application can do, checked by the build itself.

The build script trusts only this report: assumptions about the interpreter or the freezer are not evidence.
Nothing here reads or writes the user's data folder or credentials.
"""
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path

NOTICES = 'THIRD-PARTY-NOTICES.txt'
# Package data without which a start, a generation or an export fails later, far from the build.
REQUIRED_FILES = [
    ('storygen.web', 'static/i18n.json'),
    ('storygen.web', 'static/app.css'),
    ('storygen.web', 'static/favicon.svg'),
    ('storygen.web', 'templates/base.html'),
    ('storygen.storage', 'migrations/001_initial.sql'),
    ('storygen.storage', 'migrations/002_trash.sql'),
    ('storygen.storage', 'migrations/003_publication.sql'),
    ('storygen.storage', 'migrations/004_authoring_comments.sql'),
    ('storygen.storage', 'migrations/005_import_sources.sql'),
    ('storygen.generation', 'resources/brief_uk_v2.txt'),
    ('storygen.generation', 'resources/memory_delta_uk_v4.txt'),
    ('storygen.evaluation', 'resources/evaluator_uk_v1.txt'),
    ('storygen.publication', 'resources/fonts/NotoSerif-Bold.ttf'),
]


def _tls_context():
    import ssl
    ssl.create_default_context()
    import httpx
    httpx.Client().close()
    return ''


def _edition_marker():
    from . import build_edition
    return build_edition.current().edition


def _package_data():
    for package, relative in REQUIRED_FILES:
        if not files(package).joinpath(relative).is_file():
            raise LookupError(f'{package}/{relative}')
    return f'{len(REQUIRED_FILES)} файлів'


def _key_store():
    from .providers import secrets
    if secrets.default_backend() is None:
        raise LookupError('немає сховища облікових даних')
    return ''


def _tray():
    import pystray  # noqa: F401 - the import itself is the check
    from .desktop_tray import _image
    _image()
    return ''


def _database():
    import sqlite3
    from contextlib import closing
    from .storage.database import SCHEMA_VERSION
    from .storage.repository import Repository
    with tempfile.TemporaryDirectory(prefix='obscura-self-check-', ignore_cleanup_errors=True) as root:
        Repository(Path(root) / 'data')
        with closing(sqlite3.connect(Path(root) / 'data' / 'storygen.sqlite3')) as db:
            found = db.execute('PRAGMA user_version').fetchone()[0]
    if found != SCHEMA_VERSION:
        raise LookupError(f'схема {found}, очікувано {SCHEMA_VERSION}')
    return f'схема {found}'


def _licenses():
    if not getattr(sys, 'frozen', False):
        return 'не заморожена збірка'
    if not (Path(sys.executable).parent / NOTICES).is_file():
        raise LookupError(NOTICES)
    return NOTICES


CHECKS = [('tls_context', _tls_context), ('edition_marker', _edition_marker), ('package_data', _package_data),
          ('key_store', _key_store), ('tray', _tray), ('database', _database), ('licenses', _licenses)]


def _version() -> str:
    try:
        return version('storygen')
    except PackageNotFoundError:
        return '0.0.0'


def run_checks() -> dict:
    checks = []
    for name, check in CHECKS:
        try:
            checks.append({'name': name, 'ok': True, 'detail': check()})
        except LookupError as error:
            # Code-owned text: a relative package path or a short reason, never a path of the user's profile.
            checks.append({'name': name, 'ok': False, 'detail': str(error.args[0]) if error.args else 'LookupError'})
        except Exception as error:
            checks.append({'name': name, 'ok': False, 'detail': type(error).__name__})
    edition, max_rating = None, None
    try:
        from . import build_edition
        current = build_edition.current()
        edition, max_rating = current.edition, current.max_rating.model_dump()
    except Exception:
        pass
    return {'ok': all(check['ok'] for check in checks), 'frozen': bool(getattr(sys, 'frozen', False)), 'version': _version(),
            'edition': edition, 'max_rating': max_rating, 'checks': checks}
