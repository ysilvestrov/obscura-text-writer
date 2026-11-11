"""DESKTOP-001: the launcher of the installed build — data folder, file log, running-server record, second launch."""
import json
import logging
import socket
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from storygen import build_edition, desktop

pytestmark = pytest.mark.loopback


@pytest.fixture(autouse=True)
def close_desktop_logging():
    yield
    desktop.close_logging()


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Launch:
    """Runs desktop.main in a thread with a tray stand-in that blocks until released."""

    def __init__(self, data_dir, *extra, opener=None):
        self.ready, self.release, self.opened = threading.Event(), threading.Event(), []
        self.url, self.code, self.tray_args = None, None, None
        argv = ['--data-dir', str(data_dir), *extra]
        self.thread = threading.Thread(target=self._run, args=(argv, opener or self.opened.append), daemon=True)

    def _tray(self, url, data_dir, backups_dir, stop):
        self.url, self.tray_args = url, (data_dir, backups_dir)
        self.ready.set()
        self.release.wait(30)
        stop()

    def _run(self, argv, opener):
        self.code = desktop.main(argv, opener=opener, tray=self._tray)

    def __enter__(self):
        self.thread.start()
        assert self.ready.wait(30), 'launcher did not reach the tray'
        return self

    def __exit__(self, *exc):
        self.release.set()
        self.thread.join(30)
        assert not self.thread.is_alive()


def info(url):
    with urllib.request.urlopen(url + '/api/app-info', timeout=5) as response:
        return json.loads(response.read())


def test_default_data_dir_is_under_the_user_profile(monkeypatch, tmp_path):
    monkeypatch.setenv('USERPROFILE', str(tmp_path / 'Користувач Тест'))
    monkeypatch.setattr(desktop.os, 'name', 'nt')
    assert desktop.default_data_dir() == tmp_path / 'Користувач Тест' / 'Obscura'


def test_logging_goes_to_a_rotating_file_and_survives_missing_std_streams(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    log = desktop.configure_logging(tmp_path / 'Дані')
    logging.getLogger('storygen.desktop').info('перевірка')
    assert log == tmp_path / 'Дані' / 'logs' / 'obscura.log' and 'перевірка' in log.read_text(encoding='utf-8')
    desktop.configure_logging(tmp_path / 'Дані')
    logging.getLogger('storygen.desktop').info('ще раз')
    assert log.read_text(encoding='utf-8').count('ще раз') == 1


def test_choose_port_falls_back_when_the_preferred_one_is_busy():
    with socket.socket() as busy:
        busy.bind(('127.0.0.1', 0))
        busy.listen()
        taken = busy.getsockname()[1]
        chosen = desktop.choose_port(taken)
        assert chosen != taken
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', chosen))
    spare = free_port()
    assert desktop.choose_port(spare) == spare


class _Reply(BaseHTTPRequestHandler):
    body, delay = b'{}', 0

    def do_GET(self):
        time.sleep(type(self).delay)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(type(self).body)

    def log_message(self, *args):
        pass


@pytest.fixture
def other_program():
    handler = type('Handler', (_Reply,), {})
    server = HTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield handler, f'http://127.0.0.1:{server.server_address[1]}'
    server.shutdown()
    server.server_close()


def test_running_server_trusts_only_a_matching_instance(tmp_path, other_program):
    handler, url = other_program
    assert desktop.running_server(tmp_path) is None                      # no record
    desktop.write_server_record(tmp_path, url, 'A')
    record = json.loads((tmp_path / 'server.json').read_text(encoding='utf-8'))
    assert record['url'] == url and record['instance_id'] == 'A' and isinstance(record['pid'], int)
    handler.body = json.dumps({'instance_id': 'A'}).encode()
    assert desktop.running_server(tmp_path) == url
    handler.body = json.dumps({'instance_id': 'B'}).encode()             # another Obscura on the same port
    assert desktop.running_server(tmp_path) is None
    handler.body = b'<html>not json</html>'                             # another program
    assert desktop.running_server(tmp_path) is None
    handler.body, handler.delay = json.dumps({'instance_id': 'A'}).encode(), 0.6
    assert desktop.running_server(tmp_path, timeout=0.2) is None         # too slow to be trusted
    handler.delay = 0
    (tmp_path / 'server.json').write_text('{broken', encoding='utf-8')
    assert desktop.running_server(tmp_path) is None
    desktop.write_server_record(tmp_path, f'http://127.0.0.1:{free_port()}', 'A')
    assert desktop.running_server(tmp_path) is None                      # nobody listens
    desktop.write_server_record(tmp_path, 'http://example.test:80', 'A')
    assert desktop.running_server(tmp_path) is None                      # never asks a non-loopback address
    desktop.remove_server_record(tmp_path)
    desktop.remove_server_record(tmp_path)
    assert not (tmp_path / 'server.json').exists()


def test_main_starts_serves_and_cleans_up(tmp_path):
    data = tmp_path / 'Мої твори'
    with Launch(data, '--no-browser') as launch:
        record = json.loads((data / 'server.json').read_text(encoding='utf-8'))
        assert record['url'] == launch.url and info(launch.url)['instance_id'] == record['instance_id']
        assert launch.tray_args == (data, tmp_path / 'Мої твори-backups')
        port = int(launch.url.rsplit(':', 1)[1])
    assert launch.code == 0 and launch.opened == []
    assert not (data / 'server.json').exists()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', port))                                   # the port is free again
    assert launch.url in (data / 'logs' / 'obscura.log').read_text(encoding='utf-8')


def test_browser_is_opened_once_the_server_answers(tmp_path):
    with Launch(tmp_path / 'data') as launch:
        assert launch.opened == [launch.url]


def test_second_launch_opens_the_running_instance(tmp_path):
    data = tmp_path / 'data'
    with Launch(data, '--no-browser') as first:
        opened = []

        def no_tray(*args):
            raise AssertionError('the second launch must not start a server')
        assert desktop.main(['--data-dir', str(data)], opener=opened.append, tray=no_tray) == 0
        assert opened == [first.url]
        assert json.loads((data / 'server.json').read_text(encoding='utf-8'))['url'] == first.url


def test_invalid_edition_marker_is_logged_and_stops_before_data(tmp_path, monkeypatch):
    def broken():
        raise ValueError('Некоректний файл видання build_edition.json: видання для Store потребує report_url')
    monkeypatch.setattr(build_edition, 'current', broken)
    data = tmp_path / 'data'
    assert desktop.main(['--data-dir', str(data), '--no-browser', '--no-tray']) == 2
    assert 'report_url' in (data / 'logs' / 'obscura.log').read_text(encoding='utf-8')
    assert sorted(p.name for p in data.iterdir()) == ['logs']


def test_no_tray_mode_runs_until_the_server_stops(tmp_path):
    servers = []

    def serve(app, port):
        server = desktop.uvicorn_server(app, port)
        servers.append(server)
        return server
    result = {}
    thread = threading.Thread(target=lambda: result.update(code=desktop.main(
        ['--data-dir', str(tmp_path / 'data'), '--no-browser', '--no-tray'], serve=serve)), daemon=True)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline and not (servers and servers[0].started):
        time.sleep(0.05)
    assert servers and servers[0].started
    servers[0].should_exit = True
    thread.join(30)
    assert result == {'code': 0}


def test_server_that_never_starts_is_exit_code_4(tmp_path):
    class Dead:
        started, should_exit = False, False

        def run(self):
            raise RuntimeError('cannot bind')
    assert desktop.main(['--data-dir', str(tmp_path / 'data'), '--no-browser', '--no-tray'], serve=lambda app, port: Dead()) == 4
    assert not (tmp_path / 'data' / 'server.json').exists()


def test_maintenance_commands_check_the_edition_marker(tmp_path, monkeypatch, capsys):
    from storygen import maintenance

    def broken():
        raise ValueError('Некоректний файл видання build_edition.json: невідоме видання або зайві поля')
    monkeypatch.setattr(build_edition, 'current', broken)
    assert maintenance.main(['fsck', '--data-dir', str(tmp_path / 'data')]) == 1
    assert 'build_edition.json' in capsys.readouterr().out
    assert not (tmp_path / 'data').exists()


def _old_schema(tmp_path):
    from tests.storage.test_pre_migration import old_schema_dir
    return old_schema_dir(tmp_path)


def _version(data):
    import sqlite3
    with sqlite3.connect(data / 'storygen.sqlite3') as db:
        return db.execute('PRAGMA user_version').fetchone()[0]


def test_desktop_backs_up_then_migrates(tmp_path):
    from storygen.storage.database import SCHEMA_VERSION
    data = _old_schema(tmp_path)
    with Launch(data, '--no-browser'):
        assert _version(data) == SCHEMA_VERSION
    copies = list((tmp_path / (data.name + '-backups')).iterdir())
    assert len(copies) == 1 and copies[0].name.startswith('pre-migration-v4-') and _version(copies[0] / 'data') == 4
    assert str(copies[0]) in (data / 'logs' / 'obscura.log').read_text(encoding='utf-8')


def test_desktop_refuses_to_start_when_backup_fails(tmp_path):
    data = _old_schema(tmp_path)
    (tmp_path / (data.name + '-backups')).write_text('не тека', encoding='utf-8')

    def no_server(app, port):
        raise AssertionError('the server must not start without a backup')
    assert desktop.main(['--data-dir', str(data), '--no-browser', '--no-tray'], serve=no_server) == 3
    assert _version(data) == 4 and not (data / 'server.json').exists()
    assert 'Резервну копію перед оновленням бази не створено' in (data / 'logs' / 'obscura.log').read_text(encoding='utf-8')


def test_discovery_ignores_proxy_settings(tmp_path, other_program, monkeypatch):
    handler, url = other_program
    handler.body = json.dumps({'instance_id': 'A'}).encode()
    desktop.write_server_record(tmp_path, url, 'A')
    for name in ('HTTP_PROXY', 'http_proxy', 'ALL_PROXY'):
        monkeypatch.setenv(name, 'http://127.0.0.1:9')
    assert desktop.running_server(tmp_path) == url


def test_discovery_does_not_follow_redirects(tmp_path):
    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header('Location', 'http://example.test/api/app-info')
            self.end_headers()

        def log_message(self, *args):
            pass
    server = HTTPServer(('127.0.0.1', 0), Redirect)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        desktop.write_server_record(tmp_path, f'http://127.0.0.1:{server.server_address[1]}', 'A')
        assert desktop.running_server(tmp_path) is None
    finally:
        server.shutdown()
        server.server_close()


def test_stale_record_does_not_stop_a_fresh_start(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    desktop.write_server_record(data, f'http://127.0.0.1:{free_port()}', 'gone')
    with Launch(data, '--no-browser') as launch:
        record = json.loads((data / 'server.json').read_text(encoding='utf-8'))
        assert record['url'] == launch.url and record['instance_id'] != 'gone'
    assert launch.code == 0


def test_whole_launch_works_without_standard_streams(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'stdout', None)
    monkeypatch.setattr(sys, 'stderr', None)
    with Launch(tmp_path / 'data', '--no-browser') as launch:
        assert info(launch.url)['edition'] == 'full'
    assert launch.code == 0


def test_failed_second_start_keeps_the_first_record_and_opens_it(tmp_path, monkeypatch):
    # The first check misses the running instance (slow machine); the start then fails on the data folder lock.
    data = tmp_path / 'data'
    with Launch(data, '--no-browser') as first:
        real, calls = desktop.running_server, []

        def flaky(data_dir, timeout=1.0):
            calls.append(1)
            return None if len(calls) == 1 else real(data_dir, timeout)
        monkeypatch.setattr(desktop, 'running_server', flaky)
        opened, alerts = [], []
        code = desktop.main(['--data-dir', str(data), '--no-tray'], opener=opened.append, alert=alerts.append)
        assert (code, opened, alerts) == (0, [first.url], [])
        assert json.loads((data / 'server.json').read_text(encoding='utf-8'))['url'] == first.url
        assert info(first.url)['instance_id']


def test_quit_with_an_open_stream_still_shuts_the_server_down(tmp_path, monkeypatch):
    import asyncio
    from fastapi.responses import StreamingResponse
    monkeypatch.setattr(desktop, 'GRACEFUL_SHUTDOWN', 1)
    servers = []

    def serve(app, port):
        async def endless():
            while True:
                yield b'data: tick\n\n'
                await asyncio.sleep(0.05)
        app.add_api_route('/test-stream', lambda: StreamingResponse(endless(), media_type='text/event-stream'))
        servers.append(desktop.uvicorn_server(app, port))
        return servers[0]
    released, state, result = threading.Event(), {}, {}

    def tray(url, data_dir, backups, stop):
        state['stream'] = urllib.request.urlopen(url + '/test-stream', timeout=5)
        state['stream'].read(10)
        state['url'] = url
        released.wait(30)
        stop()
    data = tmp_path / 'data'
    thread = threading.Thread(target=lambda: result.update(code=desktop.main(['--data-dir', str(data), '--no-browser'], tray=tray, serve=serve)), daemon=True)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline and 'url' not in state:
        time.sleep(0.05)
    started = time.time()
    released.set()
    thread.join(20)
    assert not thread.is_alive() and result == {'code': 0} and time.time() - started < 15
    log = (data / 'logs' / 'obscura.log').read_text(encoding='utf-8')
    assert 'Сервер зупинено' in log and 'Application shutdown complete' in log
    assert not (data / 'server.json').exists()


def test_access_log_is_off_so_request_paths_stay_out_of_the_log(tmp_path):
    with Launch(tmp_path / 'data', '--no-browser') as launch:
        urllib.request.urlopen(launch.url + '/api/app-info?q=secret-search-text', timeout=5).read()
    assert 'secret-search-text' not in (tmp_path / 'data' / 'logs' / 'obscura.log').read_text(encoding='utf-8')


@pytest.mark.parametrize('case,expected', [('marker', 2), ('backup', 3), ('server', 4)])
def test_a_refused_start_tells_the_user_where_the_log_is(tmp_path, monkeypatch, case, expected):
    data = tmp_path / 'data'
    serve = None
    if case == 'marker':
        def broken():
            raise ValueError('Некоректний файл видання build_edition.json: невідоме видання або зайві поля')
        monkeypatch.setattr(build_edition, 'current', broken)
    elif case == 'backup':
        data = _old_schema(tmp_path)
        (tmp_path / (data.name + '-backups')).write_text('не тека', encoding='utf-8')
    else:
        class Dead:
            started, should_exit = False, False

            def run(self):
                raise RuntimeError('cannot bind')
        serve = lambda app, port: Dead()
    alerts = []
    assert desktop.main(['--data-dir', str(data), '--no-browser', '--no-tray'], serve=serve, alert=alerts.append) == expected
    assert len(alerts) == 1 and str(data / 'logs' / 'obscura.log') in alerts[0]


def test_logging_restores_the_root_level(tmp_path):
    before = logging.getLogger().level
    desktop.configure_logging(tmp_path / 'data')
    desktop.close_logging()
    assert logging.getLogger().level == before


def test_discovery_needs_no_tls_machinery(tmp_path, other_program, monkeypatch):
    # A frozen build may be unable to create TLS contexts at import time; asking a loopback HTTP server must not need one.
    import importlib
    import ssl

    def broken(*args, **kwargs):
        raise FileNotFoundError(2, 'No such file or directory')
    monkeypatch.setattr(ssl, 'create_default_context', broken)
    monkeypatch.setattr(ssl, '_create_default_https_context', broken)
    module = importlib.reload(desktop)
    try:
        handler, url = other_program
        handler.body = json.dumps({'instance_id': 'A'}).encode()
        module.write_server_record(tmp_path, url, 'A')
        assert module.running_server(tmp_path) == url
    finally:
        monkeypatch.undo()
        importlib.reload(desktop)


def test_env_file_option_brings_provider_keys(tmp_path, monkeypatch):
    # An installation from source keeps its keys in the repository .env; the launcher must be able to use that file.
    import os
    monkeypatch.delenv('SYNTHETIC_LAUNCHER_KEY', raising=False)
    env_file = tmp_path / 'repo' / '.env'
    env_file.parent.mkdir()
    env_file.write_text('SYNTHETIC_LAUNCHER_KEY=from-env-file\n', encoding='utf-8')
    with Launch(tmp_path / 'data', '--no-browser', '--env-file', str(env_file)):
        assert os.environ.get('SYNTHETIC_LAUNCHER_KEY') == 'from-env-file'
    monkeypatch.delenv('SYNTHETIC_LAUNCHER_KEY', raising=False)


def test_default_env_file_is_in_the_data_folder(tmp_path, monkeypatch):
    import os
    monkeypatch.delenv('SYNTHETIC_LAUNCHER_KEY', raising=False)
    data = tmp_path / 'data'
    data.mkdir()
    (data / '.env').write_text('SYNTHETIC_LAUNCHER_KEY=from-data-folder\n', encoding='utf-8')
    with Launch(data, '--no-browser'):
        assert os.environ.get('SYNTHETIC_LAUNCHER_KEY') == 'from-data-folder'
    monkeypatch.delenv('SYNTHETIC_LAUNCHER_KEY', raising=False)
