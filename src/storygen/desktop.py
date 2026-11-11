"""DESKTOP-001: launcher of the installed build — no console, a data folder in the user profile, a file log.

`storygen` (server.py) stays the developer entry point with a console. This one never writes to stdout or stderr:
a windowed executable has neither.
"""
import argparse
import json
import logging
import os
import socket
import threading
import time
import urllib.request
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

RECORD = 'server.json'
LOOPBACK = 'http://127.0.0.1:'
PREFERRED_PORT = 8765
START_TIMEOUT = 30.0
logger = logging.getLogger('storygen.desktop')
_handler = None


def default_data_dir() -> Path:
    # The profile folder itself: AppData of a packaged app is removed with the app, Documents is often synced to a cloud.
    home = Path(os.environ['USERPROFILE']) if os.name == 'nt' and os.environ.get('USERPROFILE') else Path.home()
    return home / 'Obscura'


def close_logging() -> None:
    global _handler
    if _handler is not None:
        logging.getLogger().removeHandler(_handler)
        _handler.close()
        _handler = None


def configure_logging(data_dir: Path) -> Path:
    """Send every log record to <data>/logs/obscura.log; calling it again replaces the handler."""
    global _handler
    path = Path(data_dir) / 'logs' / 'obscura.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    close_logging()
    _handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    _handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    root = logging.getLogger()
    root.addHandler(_handler)
    root.setLevel(logging.INFO)
    return path


def choose_port(preferred: int = PREFERRED_PORT) -> int:
    for candidate in (preferred, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(('127.0.0.1', candidate))
            except OSError:
                continue
            return probe.getsockname()[1]
    raise OSError('Немає вільного порту на 127.0.0.1')


def write_server_record(data_dir: Path, url: str, instance_id: str) -> None:
    path = Path(data_dir) / RECORD
    temporary = path.with_name(RECORD + '.tmp')
    temporary.write_text(json.dumps({'url': url, 'instance_id': instance_id, 'pid': os.getpid()}), encoding='utf-8')
    os.replace(temporary, path)


def remove_server_record(data_dir: Path) -> None:
    (Path(data_dir) / RECORD).unlink(missing_ok=True)


def running_server(data_dir: Path, timeout: float = 1.0) -> str | None:
    """Address of the server already running over this data folder, or None.

    The record alone proves nothing: the process may have died and another program may listen on that port. Only a
    loopback server that answers with the recorded instance id is this folder's server."""
    try:
        record = json.loads((Path(data_dir) / RECORD).read_text(encoding='utf-8'))
        url, instance_id = record['url'], record['instance_id']
        if not (isinstance(url, str) and url.startswith(LOOPBACK) and url[len(LOOPBACK):].isdigit() and isinstance(instance_id, str)):
            return None
        with urllib.request.urlopen(url + '/api/app-info', timeout=timeout) as response:
            answer = json.loads(response.read(65536))
        return url if isinstance(answer, dict) and answer.get('instance_id') == instance_id else None
    except Exception:
        return None


def uvicorn_server(app, port: int):
    import uvicorn
    # log_config=None: uvicorn's default config writes to stderr, which a windowed process does not have.
    return uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, workers=1, log_config=None))


def _wait_until_started(server, thread) -> bool:
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if server.started:
            return True
        if not thread.is_alive():
            return False
        time.sleep(0.05)
    return False


def main(argv=None, *, opener=webbrowser.open, tray=None, serve=None) -> int:
    """Exit codes: 0 — ran or already running, 2 — invalid build edition marker, 3 — no backup before a migration,
    4 — the server did not start."""
    parser = argparse.ArgumentParser(description='Obscura Text Writer')
    parser.add_argument('--data-dir', type=Path, default=None)
    parser.add_argument('--no-tray', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    data_dir = (args.data_dir or default_data_dir()).resolve()
    configure_logging(data_dir)
    try:
        return _run(args, data_dir, opener, tray, serve or uvicorn_server)
    except Exception:
        logger.exception('Запуск зупинено через непередбачену помилку')
        return 4
    finally:
        close_logging()


def _run(args, data_dir: Path, opener, tray, serve) -> int:
    from . import build_edition
    try:
        build_edition.current()
    except ValueError as error:
        # BUILD-EDITION-001-S04: nothing but the log is created for a build with a broken marker.
        logger.error('%s', error)
        return 2
    url = running_server(data_dir)
    if url:
        logger.info('Сервер цієї теки даних уже працює: %s', url)
        if not args.no_browser:
            opener(url)
        return 0
    from .application.settings import AppSettings
    from .storage.pre_migration import PreMigrationBackupFailed, backup_before_migration
    from .web.app import create_app
    try:
        copy = backup_before_migration(data_dir)
    except PreMigrationBackupFailed as error:
        # DESKTOP-001-S03: without a verified copy the database is not opened, so it is not migrated.
        logger.error('%s', error)
        return 3
    if copy is not None:
        logger.info('Перед оновленням бази створено резервну копію: %s', copy)
    port = choose_port()
    app = create_app(AppSettings(data_dir=data_dir, env_file=data_dir / '.env', port=port))
    server = serve(app, port)
    thread = threading.Thread(target=_serve, args=(server,), name='obscura-server', daemon=True)
    thread.start()

    def stop():
        server.should_exit = True
    try:
        if not _wait_until_started(server, thread):
            logger.error('Сервер не стартував на порту %s', port)
            return 4
        url = f'{LOOPBACK}{port}'
        write_server_record(data_dir, url, app.state.instance_id)
        logger.info('Сервер працює: %s; тека даних: %s', url, data_dir)
        if not args.no_browser:
            opener(url)
        if not args.no_tray:
            from .desktop_tray import TrayUnavailable, run_tray
            from .storage.pre_migration import backups_dir
            try:
                # Blocks until "Quit"; a stand-in is injected by tests.
                (tray or run_tray)(url, data_dir, backups_dir(data_dir), stop)
                return 0
            except TrayUnavailable:
                logger.warning('Значок у треї недоступний; застосунок працює без нього, доки процес не зупинять')
        while thread.is_alive():
            thread.join(0.5)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        stop()
        thread.join(15)
        remove_server_record(data_dir)
        logger.info('Сервер зупинено')


def _serve(server) -> None:
    try:
        server.run()
    except Exception:
        logger.exception('Сервер завершився з помилкою')


if __name__ == '__main__':
    raise SystemExit(main())
