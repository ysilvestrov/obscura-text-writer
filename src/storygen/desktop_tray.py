"""DESKTOP-001-S04: the tray icon of the installed build — the only visible handle of a process without a window."""
import locale
import os
import webbrowser
from pathlib import Path
from typing import Callable

from .web.localization import translate


class TrayUnavailable(RuntimeError):
    """The optional tray library (extra `desktop`) is missing or cannot start on this system."""


def system_locale() -> str:
    try:
        name = (locale.getlocale()[0] or '').lower()
    except Exception:
        name = ''
    return 'uk' if name.startswith(('uk', 'ukrainian')) else 'en'


def reveal(path: Path) -> None:
    if os.name == 'nt':
        os.startfile(str(path))  # noqa: S606 - opens a folder of this application in Explorer
    else:
        webbrowser.open(Path(path).as_uri())


def menu_items(url: str, data_dir: Path, backups_dir: Path, stop: Callable[[], None], *, opener=webbrowser.open,
               reveal=reveal, locale: str = 'uk') -> list[tuple[str, Callable[[], None]]]:
    """Labels and actions in menu order; the first one is the default (double-click) action."""
    items = [(translate('desktop.tray.open', locale), lambda: opener(url)),
             (translate('desktop.tray.folder', locale), lambda: reveal(data_dir))]
    if Path(backups_dir).is_dir():
        items.append((translate('desktop.tray.backups', locale), lambda: reveal(backups_dir)))
    items.append((translate('desktop.tray.quit', locale), stop))
    return items


def _image():
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (64, 64), (92, 26, 43))
    draw = ImageDraw.Draw(image)
    draw.ellipse((14, 14, 50, 50), outline=(245, 238, 228), width=6)
    return image


def run_tray(url: str, data_dir: Path, backups_dir: Path, stop: Callable[[], None]) -> None:
    """Show the icon and block until "Quit"; raises TrayUnavailable when there is no tray to show."""
    try:
        import pystray
        image = _image()
    except Exception:
        raise TrayUnavailable() from None
    holder = {}

    def quit_application():
        stop()
        holder['icon'].stop()
    items = menu_items(url, data_dir, backups_dir, quit_application, locale=system_locale())
    menu = pystray.Menu(*[pystray.MenuItem(label, (lambda action: lambda icon, item: action())(action), default=index == 0)
                          for index, (label, action) in enumerate(items)])
    holder['icon'] = pystray.Icon('Obscura', image, 'Obscura', menu=menu)
    try:
        holder['icon'].run()
    except Exception:
        raise TrayUnavailable() from None
