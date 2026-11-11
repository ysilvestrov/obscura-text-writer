"""DESKTOP-001-S04: tray menu of the installed build."""
import sys
import threading
import time
import types

import pytest

from storygen import desktop, desktop_tray
from storygen.desktop_tray import TrayUnavailable, menu_items, run_tray


def labels(items):
    return [label for label, _ in items]


def test_menu_labels_order_and_actions(tmp_path):
    calls = []
    data, backups = tmp_path / 'Obscura', tmp_path / 'Obscura-backups'
    data.mkdir()
    items = menu_items('http://127.0.0.1:8765', data, backups, lambda: calls.append('stop'),
                       opener=lambda url: calls.append(('open', url)), reveal=lambda path: calls.append(('reveal', path)), locale='uk')
    assert labels(items) == ['Відкрити Obscura', 'Тека творів', 'Вийти']
    for _, action in items:
        action()
    assert calls == [('open', 'http://127.0.0.1:8765'), ('reveal', data), 'stop']
    english = menu_items('u', data, backups, lambda: None, locale='en')
    assert labels(english) == ['Open Obscura', 'Stories folder', 'Quit']


def test_backups_item_appears_once_there_are_backups(tmp_path):
    calls = []
    data, backups = tmp_path / 'Obscura', tmp_path / 'Obscura-backups'
    backups.mkdir()
    items = menu_items('u', data, backups, lambda: None, reveal=calls.append, locale='uk')
    assert labels(items) == ['Відкрити Obscura', 'Тека творів', 'Резервні копії', 'Вийти']
    items[2][1]()
    assert calls == [backups]
    assert labels(menu_items('u', data, backups, lambda: None, locale='en'))[2] == 'Backups'


@pytest.mark.parametrize('name,expected', [('Ukrainian_Ukraine', 'uk'), ('uk_UA', 'uk'), ('English_United States', 'en'),
                                           ('pl_PL', 'en'), (None, 'en')])
def test_menu_language_follows_the_system(monkeypatch, name, expected):
    monkeypatch.setattr(desktop_tray.locale, 'getlocale', lambda: (name, 'cp1251'))
    assert desktop_tray.system_locale() == expected


class FakePystray(types.ModuleType):
    def __init__(self):
        super().__init__('pystray')
        self.icons = []
        outer = self

        class MenuItem:
            def __init__(self, text, action, default=False):
                self.text, self.action, self.default = text, action, default

        class Menu:
            def __init__(self, *items):
                self.items = items

        class Icon:
            def __init__(self, name, image, title, menu=None):
                self.name, self.image, self.title, self.menu = name, image, title, menu
                self.stopped = threading.Event()
                outer.icons.append(self)

            def run(self):
                self.stopped.wait(10)

            def stop(self):
                self.stopped.set()
        self.MenuItem, self.Menu, self.Icon = MenuItem, Menu, Icon


def test_run_tray_builds_the_icon_and_quit_stops_everything(tmp_path, monkeypatch):
    pytest.importorskip('PIL')
    fake = FakePystray()
    monkeypatch.setitem(sys.modules, 'pystray', fake)
    monkeypatch.setattr(desktop_tray, 'system_locale', lambda: 'uk')
    stops = []
    thread = threading.Thread(target=run_tray, args=('http://127.0.0.1:1', tmp_path, tmp_path / 'none', lambda: stops.append(1)), daemon=True)
    thread.start()
    deadline = time.time() + 5
    while time.time() < deadline and not fake.icons:
        time.sleep(0.01)
    icon = fake.icons[0]
    assert (icon.name, icon.title) == ('Obscura', 'Obscura') and icon.image.size == (64, 64)
    assert [item.text for item in icon.menu.items] == ['Відкрити Obscura', 'Тека творів', 'Вийти']
    assert [item.default for item in icon.menu.items] == [True, False, False]
    icon.menu.items[-1].action(icon, icon.menu.items[-1])
    thread.join(5)
    assert not thread.is_alive() and stops == [1] and icon.stopped.is_set()


def test_missing_tray_library_is_reported(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'pystray', None)
    with pytest.raises(TrayUnavailable):
        run_tray('u', tmp_path, tmp_path, lambda: None)


@pytest.mark.loopback
def test_launcher_without_a_tray_keeps_running_and_logs_it(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, 'pystray', None)
    servers = []

    def serve(app, port):
        servers.append(desktop.uvicorn_server(app, port))
        return servers[0]
    result = {}
    data = tmp_path / 'data'
    thread = threading.Thread(target=lambda: result.update(code=desktop.main(['--data-dir', str(data), '--no-browser'], serve=serve)), daemon=True)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline and not (servers and servers[0].started and (data / 'server.json').exists()):
        time.sleep(0.05)
    time.sleep(0.3)
    assert thread.is_alive(), 'the launcher must keep serving without a tray'
    servers[0].should_exit = True
    thread.join(30)
    assert result == {'code': 0}
    assert 'Значок у треї недоступний' in (data / 'logs' / 'obscura.log').read_text(encoding='utf-8')
