"""Build edition of the application: 'full' (default) or 'store' (Microsoft Store rules, rating limit).

The marker file is put into the package by the build script only; a source checkout has none and is the full edition.
"edition" alone already names a book edition in publication, hence build_edition everywhere.
"""
import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ValidationError

from .domain import ContentRating, DomainModel
from .rating.levels import higher_axes

MARKER = 'build_edition.json'
INVALID = 'Некоректний файл видання build_edition.json: {reason}'
LIMITS = {'full': ContentRating(sexual=2, violence=2, themes=2), 'store': ContentRating(sexual=1, violence=2, themes=2)}
URL_FIELDS = ('support_url', 'waitlist_url', 'report_url')


class BuildEdition(DomainModel):
    edition: Literal['full', 'store'] = 'full'
    support_url: str = ''
    waitlist_url: str = ''
    report_url: str = ''

    @property
    def max_rating(self) -> ContentRating:
        return LIMITS[self.edition]


def _clean_https(url: str) -> bool:
    # The interface renders these as links: lowercase https, a host, no whitespace or control characters.
    if not url.startswith('https://') or any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7f for ch in url):
        return False
    try:
        return bool(urlsplit(url).hostname)
    except ValueError:
        return False


def load_build_edition(path: Path | None = None) -> BuildEdition:
    """A missing marker is the full edition; anything unreadable is an error, never a silent fallback."""
    source = files(__package__).joinpath(MARKER) if path is None else Path(path)
    if not source.is_file():
        # Present but not a regular file is unreadable, not absent.
        if source.is_dir():
            raise ValueError(INVALID.format(reason='це не файл'))
        return BuildEdition()
    try:
        text = source.read_text(encoding='utf-8')
    except (OSError, ValueError):
        raise ValueError(INVALID.format(reason='файл не читається як JSON')) from None
    return parse_build_edition(text)


def parse_build_edition(text: str) -> BuildEdition:
    """The marker's rules, applied to its text: the build script validates with exactly what the application reads."""
    # Reasons never quote the file: it is build configuration, not something to echo into logs or pages.
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError(INVALID.format(reason='файл не читається як JSON')) from None
    try:
        loaded = BuildEdition.model_validate(data)
    except ValidationError:
        raise ValueError(INVALID.format(reason='невідоме видання або зайві поля')) from None
    if any(url and not _clean_https(url) for url in (getattr(loaded, name) for name in URL_FIELDS)):
        raise ValueError(INVALID.format(reason='адреси мають починатися з https:// і містити хост без пробілів'))
    if loaded.edition == 'store' and not loaded.report_url:
        raise ValueError(INVALID.format(reason='видання для Store потребує report_url'))
    return loaded


@lru_cache(maxsize=1)
def current() -> BuildEdition:
    return load_build_edition()


def over_limit(rating: ContentRating) -> list[str]:
    """Axes where the rating is above what this build edition allows, in AXES order."""
    return higher_axes(rating, current().max_rating)
