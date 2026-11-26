"""LONG-PROSE-TRIAL (R-47): one free trial of long prose per data folder in an edition without it.

The marker lives in app_settings: created once by insertion, `kind`, `id` and `claimed_at` never change, a series trial's
`books` only grows up to two and nothing is ever removed. Editions with long prose never read or write it. It is not a
defence against bypassing: a new data folder or a build from source gives everything anyway.
"""
import json
from datetime import datetime
from typing import Literal

from .. import build_edition
from ..domain import DomainModel

KEY = 'long_prose_trial'
MAX_BOOKS = 2


class Trial(DomainModel):
    kind: Literal['story', 'series']
    id: str
    claimed_at: str
    books: list[str] = []


def read_trial(db) -> Trial | None:
    row = db.execute('SELECT payload FROM app_settings WHERE key=?', (KEY,)).fetchone()
    return Trial.model_validate_json(row[0]) if row else None


def trial(repo) -> Trial | None:
    with repo.db.connection() as db:
        return read_trial(db)


def claim(db, kind: Literal['story', 'series'], id: str, books: list[str], now: datetime) -> Trial:
    """On an open transaction: write the marker, or ValueError(TRIAL_USED) when there already is one."""
    from ..book.guard import TRIAL_SERIES_FULL, TRIAL_USED
    if len(books) > MAX_BOOKS:
        raise ValueError(TRIAL_SERIES_FULL)
    item = Trial(kind=kind, id=id, claimed_at=now.isoformat(), books=list(books) if kind == 'series' else [])
    cursor = db.execute('INSERT INTO app_settings(key,payload) VALUES(?,?) ON CONFLICT(key) DO NOTHING',
                        (KEY, item.model_dump_json()))
    if cursor.rowcount != 1:
        raise ValueError(TRIAL_USED)
    return item


def admit(db, series_id: str, story_id: str) -> None:
    """On an open transaction: a book entering the trial series takes a place in `books`; a full list refuses it.
    Nothing to do with long prose in the edition, or for any other series."""
    if build_edition.current().long_prose:
        return
    item = read_trial(db)
    if item is None or item.kind != 'series' or item.id != series_id or story_id in item.books:
        return
    from ..book.guard import TRIAL_SERIES_FULL
    if len(item.books) >= MAX_BOOKS:
        raise ValueError(TRIAL_SERIES_FULL)
    item = item.model_copy(update={'books': [*item.books, story_id]})
    db.execute('UPDATE app_settings SET payload=? WHERE key=?', (item.model_dump_json(), KEY))


def trial_state(repo) -> dict:
    """{'state': 'none' | 'available' | 'used', kind, id, title}; 'none' in an edition with long prose (no database read)."""
    if build_edition.current().long_prose:
        return {'state': 'none', 'kind': None, 'id': None, 'title': None}
    with repo.db.connection() as db:
        item = read_trial(db)
        if item is None:
            return {'state': 'available', 'kind': None, 'id': None, 'title': None}
        table = 'stories' if item.kind == 'story' else 'series'
        row = db.execute(f'SELECT payload FROM {table} WHERE id=?', (item.id,)).fetchone()
    title = json.loads(row[0]).get('title') if row else None
    return {'state': 'used', 'kind': item.kind, 'id': item.id, 'title': title}
