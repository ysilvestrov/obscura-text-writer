"""Verified cold backups and restore into a new directory only."""
import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from ..domain import now
from .files import FileStore
from .integrity import check_integrity, contained_path, readonly_database, regular_files
from .locking import AppInstanceLock


EXCLUDED = {'worker.lock', 'storygen.sqlite3-wal', 'storygen.sqlite3-shm', 'storygen.sqlite3-journal'}


def new_destination(source: Path, destination: Path) -> Path:
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Каталог призначення вже існує')
    destination = destination.resolve()
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('Джерело й призначення не можуть бути вкладеними')
    if not destination.parent.is_dir():
        raise ValueError('Батьківський каталог призначення має існувати')
    return destination


def require_integrity(root):
    report = check_integrity(root)
    if not report.ok:
        raise ValueError('Перевірка цілісності не пройдена: ' + ', '.join(sorted({i.code for i in report.issues})))


def inventory(root):
    return [
        {'path': p.relative_to(root).as_posix(), 'size': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in regular_files(root)
    ]


def write_manifest(root, manifest):
    FileStore(root).write('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8'))


def create_backup(source: Path, destination: Path) -> Path:
    source = Path(source).resolve()
    if not (source / 'storygen.sqlite3').is_file():
        raise ValueError('База даних відсутня')
    if (source / '.restore-incomplete.json').exists():
        raise ValueError('Незавершене відновлення не може бути джерелом резерву')
    destination = new_destination(source, destination)
    regular_files(source)  # Reject links, including worker.lock, before opening it.
    with AppInstanceLock(source):
        require_integrity(source)
        source_files = regular_files(source)
        destination.mkdir()
        manifest = {'format_version': 1, 'status': 'incomplete', 'created_at': now(), 'files': []}
        write_manifest(destination, manifest)
        data = destination / 'data'
        data.mkdir()
        source_db = readonly_database(source / 'storygen.sqlite3')
        try:
            with closing(sqlite3.connect(data / 'storygen.sqlite3')) as target_db:
                source_db.backup(target_db)
        finally:
            source_db.close()
        for path in source_files:
            relative = path.relative_to(source)
            if relative.as_posix() in EXCLUDED | {'storygen.sqlite3'}:
                continue
            target = data / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        require_integrity(data)
        manifest['files'] = inventory(data)
        manifest['status'] = 'complete'
        write_manifest(destination, manifest)
    return destination


def verified_backup(backup: Path) -> tuple[Path, dict]:
    backup = Path(backup).resolve()
    try:
        files = regular_files(backup)
        if any(p.relative_to(backup).as_posix() != 'manifest.json' and p.relative_to(backup).parts[0] != 'data' for p in files):
            raise ValueError('Неочікувані файли поза data/ у резерві')
        manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
        if manifest['format_version'] != 1 or manifest['status'] != 'complete':
            raise ValueError('Резерв неповний або несумісний')
        data = backup / 'data'
        seen = set()
        for item in manifest['files']:
            path = contained_path(data, item['path'])
            relative = path.relative_to(data).as_posix()
            if relative != item['path'] or relative in seen:
                raise ValueError('Повторний або неканонічний шлях у manifest')
            seen.add(relative)
        if manifest['files'] != inventory(data):
            raise ValueError('Файли резерву не відповідають manifest')
        require_integrity(data)
        return data, manifest
    except (OSError, KeyError, TypeError) as exc:
        raise ValueError('Невірна структура резерву') from exc


def restore_backup(backup: Path, destination: Path) -> Path:
    backup = Path(backup).resolve()
    destination = new_destination(backup, destination)
    data, manifest = verified_backup(backup)
    destination.mkdir()
    marker = destination / '.restore-incomplete.json'
    FileStore(destination).write(marker.name, json.dumps({'status': 'incomplete', 'created_at': now()}).encode())
    for item in manifest['files']:
        path = contained_path(data, item['path'])
        target = contained_path(destination, item['path'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    require_integrity(destination)
    if [entry for entry in inventory(destination) if entry['path'] != marker.name] != manifest['files']:
        raise ValueError('Відновлені файли не відповідають резерву')
    marker.unlink()
    return destination
