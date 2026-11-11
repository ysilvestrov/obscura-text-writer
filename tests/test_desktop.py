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
