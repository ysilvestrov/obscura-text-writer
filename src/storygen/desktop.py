"""DESKTOP-001: launcher of the installed build — no console, a data folder in the user profile, a file log.

`storygen` (server.py) stays the developer entry point with a console. This one never relies on stdout or stderr:
a windowed executable has neither.
"""
import argparse
import json
import logging
import os
import socket
import sys
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
# Seconds uvicorn waits for open connections (the run event stream) before it closes them and shuts the app down.
GRACEFUL_SHUTDOWN = 5
STOP_TIMEOUT = 30.0
logger = logging.getLogger('storygen.desktop')
_handler = None
_previous_level = None


def default_data_dir() -> Path:
    # The profile folder itself: AppData of a packaged app is removed with the app, Documents is often synced to a cloud.
    home = Path(os.environ['USERPROFILE']) if os.name == 'nt' and os.environ.get('USERPROFILE') else Path.home()
    return home / 'Obscura'


def close_logging() -> None:
    global _handler, _previous_level
    if _handler is not None:
        root = logging.getLogger()
        root.removeHandler(_handler)
        _handler.close()
        _handler = None
        if _previous_level is not None:
            root.setLevel(_previous_level)
            _previous_level = None


def configure_logging(data_dir: Path) -> Path:
    """Send every log record to <data>/logs/obscura.log; calling it again replaces the handler."""
    global _handler, _previous_level
    path = Path(data_dir) / 'logs' / 'obscura.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    close_logging()
    root = logging.getLogger()
    _handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    _handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    _previous_level = root.level
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


# The question goes straight to this computer: no system or environment proxy, no redirect to another address.
_local = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def running_server(data_dir: Path, timeout: float = 1.0) -> str | None:
    """Address of the server already running over this data folder, or None.

    The record alone proves nothing: the process may have died and another program may listen on that port. Only a
    loopback server that answers with the recorded instance id is this folder's server."""
    try:
        record = json.loads((Path(data_dir) / RECORD).read_text(encoding='utf-8'))
        url, instance_id = record['url'], record['instance_id']
        port = url[len(LOOPBACK):] if isinstance(url, str) and url.startswith(LOOPBACK) else ''
        if not (port.isascii() and port.isdigit() and isinstance(instance_id, str)):
            return None
        with _local.open(url + '/api/app-info', timeout=timeout) as response:
            answer = json.loads(response.read(65536))
        return url if isinstance(answer, dict) and answer.get('instance_id') == instance_id else None
    except Exception:
        return None


def uvicorn_server(app, port: int):
    import uvicorn
    # log_config=None: uvicorn's default config writes to stderr, which a windowed process does not have.
    # access_log=False: request lines carry search text and file names that do not belong in a support log.
    # timeout_graceful_shutdown: an open run event stream must not keep "Quit" from reaching the app shutdown.
    return uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, workers=1, log_config=None, access_log=False,
                                         timeout_graceful_shutdown=GRACEFUL_SHUTDOWN))


def _default_alert(text: str) -> None:
    """Tell the person why nothing opened: a message box for a windowed process, stderr for a console one."""
    try:
        if sys.stderr is not None:
            print(text, file=sys.stderr)
        elif os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, text, 'Obscura', 0x10)
    except Exception:
        pass


def _wait_until_started(server, thread) -> bool:
    deadline = time.monotonic() + START_TIMEOUT
    while time.monotonic() < deadline:
        if server.started:
            return True
        if not thread.is_alive():
            return False
        time.sleep(0.05)
    return False


def _already_running(data_dir: Path, seconds: float) -> str | None:
    deadline = time.monotonic() + seconds
    while True:
        url = running_server(data_dir)
        if url or time.monotonic() >= deadline:
            return url
        time.sleep(0.5)


def main(argv=None, *, opener=webbrowser.open, tray=None, serve=None, alert=None) -> int:
    """Exit codes: 0 — ran or already running, 2 — invalid build edition marker, 3 — no backup before a migration,
    4 — the server did not start. A refused start is reported through `alert` with the path of the log."""
    parser = argparse.ArgumentParser(description='Obscura Text Writer')
    parser.add_argument('--data-dir', type=Path, default=None)
    parser.add_argument('--no-tray', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args(argv)
    alert = alert or _default_alert
    data_dir = (args.data_dir or default_data_dir()).resolve()
    try:
        log = configure_logging(data_dir)
    except OSError as error:
        alert(f'Obscura не може створити теку даних {data_dir}: {type(error).__name__}')
        return 4
    try:
        code, reason = _run(args, data_dir, opener, tray, serve or uvicorn_server)
    except Exception:
        logger.exception('Запуск зупинено через непередбачену помилку')
        code, reason = 4, 'Запуск зупинено через непередбачену помилку.'
    finally:
        close_logging()
    if code:
        alert(f'{reason}\n\nПодробиці в журналі: {log}')
    return code


def _run(args, data_dir: Path, opener, tray, serve) -> tuple[int, str | None]:
    from . import build_edition
    try:
        build_edition.current()
    except ValueError as error:
        # BUILD-EDITION-001-S04: nothing but the log is created for a build with a broken marker.
        logger.error('%s', error)
        return 2, str(error)

    def open_page(url):
        if not args.no_browser:
            opener(url)
    url = running_server(data_dir)
    if url:
        logger.info('Сервер цієї теки даних уже працює: %s', url)
        open_page(url)
        return 0, None
    from .application.settings import AppSettings
    from .storage.pre_migration import PreMigrationBackupFailed, backup_before_migration
    from .web.app import create_app
    try:
        copy = backup_before_migration(data_dir)
    except PreMigrationBackupFailed as error:
        # DESKTOP-001-S03: without a verified copy the database is not opened, so it is not migrated.
        logger.error('%s', error)
        return 3, str(error)
    if copy is not None:
        logger.info('Перед оновленням бази створено резервну копію: %s', copy)
    port = choose_port()
    app = create_app(AppSettings(data_dir=data_dir, env_file=data_dir / '.env', port=port))
    server = serve(app, port)
    thread = threading.Thread(target=_serve, args=(server,), name='obscura-server', daemon=True)
    thread.start()
    wrote_record = False

    def stop():
        server.should_exit = True
    try:
        if not _wait_until_started(server, thread):
            # Most often another launch of this very folder won the race for the data folder lock: open that one.
            url = _already_running(data_dir, 5.0)
            if url:
                logger.info('Сервер цієї теки даних уже працює: %s', url)
                open_page(url)
                return 0, None
            logger.error('Сервер не стартував на порту %s', port)
            return 4, 'Obscura не вдалося запустити.'
        url = f'{LOOPBACK}{port}'
        write_server_record(data_dir, url, app.state.instance_id)
        wrote_record = True
        logger.info('Сервер працює: %s; тека даних: %s', url, data_dir)
        open_page(url)
        if not args.no_tray:
            from .desktop_tray import TrayUnavailable, run_tray
            from .storage.pre_migration import backups_dir
            try:
                # Blocks until "Quit"; a stand-in is injected by tests.
                (tray or run_tray)(url, data_dir, backups_dir(data_dir), stop)
                return 0, None
            except TrayUnavailable:
                logger.warning('Значок у треї недоступний; застосунок працює без нього, доки процес не зупинять')
        while thread.is_alive():
            thread.join(0.5)
        return 0, None
    except KeyboardInterrupt:
        return 0, None
    finally:
        stop()
        thread.join(STOP_TIMEOUT)
        # Only the record this process wrote is its to remove: a failed second start must not hide the first instance.
        if wrote_record:
            remove_server_record(data_dir)
        if thread.is_alive():
            logger.error('Сервер не завершився за %s с; процес завершується примусово', int(STOP_TIMEOUT))
        else:
            logger.info('Сервер зупинено')


def _serve(server) -> None:
    try:
        server.run()
    except BaseException:  # uvicorn exits the thread with SystemExit when it cannot bind
        logger.exception('Сервер завершився з помилкою')


if __name__ == '__main__':
    raise SystemExit(main())
