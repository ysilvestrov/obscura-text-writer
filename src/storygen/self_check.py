"""PACKAGING-001-S01: what a built application can do, checked by the build itself.

The build script trusts only this report: assumptions about the interpreter or the freezer are not evidence.
Nothing here reads or writes the user's data folder or credentials, opens a network connection or shows a window.
"""
import hashlib
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

NOTICES = 'THIRD-PARTY-NOTICES.txt'
# Used only without a build manifest (a source checkout): a frozen build is checked file by file against the manifest.
REQUIRED_FILES = [
    ('storygen.web', 'static/i18n.json'),
    ('storygen.web', 'static/app.css'),
    ('storygen.web', 'templates/base.html'),
    ('storygen.storage', 'migrations/001_initial.sql'),
    ('storygen.generation', 'resources/memory_delta_uk_v4.txt'),
    ('storygen.evaluation', 'resources/evaluator_uk_v1.txt'),
    ('storygen.publication', 'resources/fonts/NotoSerif-Bold.ttf'),
]


class CheckFailed(Exception):
    """A failure whose text is written by this module and is safe to put into the report."""


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
    from . import build_manifest
    manifest = build_manifest.load()
    if manifest is None:
        for package, relative in REQUIRED_FILES:
            if not files(package).joinpath(relative).is_file():
                raise CheckFailed(f'{package}/{relative}')
        return f'{len(REQUIRED_FILES)} файлів, без маніфесту збірки'
    root = files(__package__)
    for relative, digest in manifest['files'].items():
        source = root.joinpath(relative)
        if not source.is_file():
            raise CheckFailed(f'немає файла {relative}')
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise CheckFailed(f'файл відрізняється від робочої копії: {relative}')
    return f"{len(manifest['files'])} файлів за маніфестом збірки"


def _key_store():
    from .providers import secrets
    if secrets.default_backend() is None:
        raise CheckFailed('немає сховища облікових даних')
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
        raise CheckFailed(f'схема {found}, очікувано {SCHEMA_VERSION}')
    return f'схема {found}'


def _licenses():
    if not getattr(sys, 'frozen', False):
        return 'не заморожена збірка'
    if not (Path(sys.executable).parent / NOTICES).is_file():
        raise CheckFailed(NOTICES)
    return NOTICES


CHECKS = [('tls_context', _tls_context), ('edition_marker', _edition_marker), ('package_data', _package_data),
          ('key_store', _key_store), ('tray', _tray), ('database', _database), ('licenses', _licenses)]
CHECK_NAMES = [name for name, _ in CHECKS]


def run_checks() -> dict:
    checks = []
    for name, check in CHECKS:
        try:
            checks.append({'name': name, 'ok': True, 'detail': check()})
        except CheckFailed as error:
            checks.append({'name': name, 'ok': False, 'detail': str(error)})
        except Exception as error:
            # Foreign exception texts may carry paths of the user's profile: only the class name is reported.
            checks.append({'name': name, 'ok': False, 'detail': type(error).__name__})
    edition, max_rating, version = None, None, None
    try:
        from . import build_edition
        current = build_edition.current()
        edition, max_rating = current.edition, current.max_rating.model_dump()
    except Exception:
        pass
    try:
        from .build_manifest import project_version
        version = project_version()
    except Exception:
        pass
    return {'ok': all(check['ok'] for check in checks), 'frozen': bool(getattr(sys, 'frozen', False)), 'version': version,
            'edition': edition, 'max_rating': max_rating, 'checks': checks}
