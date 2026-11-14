"""SERIES storage: the series table (CAS on its revision) and the series fields of a book (CAS on the story revision)."""
from ..domain import RevisionConflict, SeriesStart, Story, new_id
from ..scene_description import name_key
from ..series_models import Series

SERIES_TITLE_TAKEN = 'Серія з такою назвою вже є'
SERIES_NUMBER_TAKEN = 'Номер {number} у серії вже зайнятий'
SERIES_NOT_EMPTY = 'Серію можна видалити лише без книг, зокрема в кошику'
SERIES_PAIR = 'Серія й номер задаються разом'
SERIES_MISSING = 'Серії не знайдено'
CONFLICT = 'Серію вже змінено. Відкрийте її заново.'
STORY_CONFLICT = 'Твір уже змінено. Відкрийте його заново.'


def _rows(db) -> list[Series]:
    return [Series.model_validate_json(r[0]) for r in db.execute('SELECT payload FROM series ORDER BY rowid')]


def _get(db, id) -> Series:
    row = db.execute('SELECT payload FROM series WHERE id=?', (id,)).fetchone()
    if not row:
        raise KeyError(SERIES_MISSING)
    return Series.model_validate_json(row[0])


def _require_title(db, title, own_id=None):
    key = name_key(' '.join(title.split()))
    if any(name_key(s.title) == key and s.id != own_id for s in _rows(db)):
        raise ValueError(SERIES_TITLE_TAKEN)


def _books(db, series_id) -> list[Story]:
    stories = [Story.model_validate_json(r[0]) for r in db.execute('SELECT payload FROM stories')]
    return sorted((s for s in stories if s.series_id == series_id), key=lambda s: s.series_number or 0)


def list_series(repo) -> list[Series]:
    with repo.db.connection() as db:
        return _rows(db)


def get_series(repo, id) -> Series:
    with repo.db.connection() as db:
        return _get(db, id)


def find_series(repo, title) -> Series | None:
    key = name_key(' '.join(title.split()))
    return next((s for s in list_series(repo) if name_key(s.title) == key), None)


def series_books(repo, id) -> list[Story]:
    """Books of the series in release order, including trashed ones."""
    with repo.db.connection() as db:
        return _books(db, id)


def create_series(repo, title: str) -> Series:
    item = Series(id=new_id(), title=title)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        _require_title(db, item.title)
        db.execute('INSERT INTO series(id,revision,payload) VALUES(?,?,?)', (item.id, item.revision, item.model_dump_json()))
    return item


def rename_series(repo, id: str, title: str, expected_revision: int) -> Series:
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        item = _get(db, id)
        if item.revision != expected_revision:
            raise RevisionConflict(CONFLICT)
        item = Series(id=item.id, revision=item.revision + 1, title=title, created_at=item.created_at)
        _require_title(db, item.title, own_id=id)
        db.execute('UPDATE series SET revision=?,payload=? WHERE id=?', (item.revision, item.model_dump_json(), id))
    return item


def delete_series(repo, id: str, expected_revision: int) -> None:
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        item = _get(db, id)
        if item.revision != expected_revision:
            raise RevisionConflict(CONFLICT)
        if _books(db, id):
            raise ValueError(SERIES_NOT_EMPTY)
        db.execute('DELETE FROM series WHERE id=?', (id,))


def set_story_series(repo, story_id: str, series_id: str | None, number: int | None, start: SeriesStart | None,
                     expected_revision: int) -> Story:
    """Put the book into a series, change its number or `Початок`, or take it out (all three None). Entering a series
    takes the start snapshot when the source book has a summary (SERIES, Task 3)."""
    if (series_id is None) != (number is None) or (series_id is None and start is not None):
        raise ValueError(SERIES_PAIR)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        if story.revision != expected_revision:
            raise RevisionConflict(STORY_CONFLICT)
        entering = series_id is not None and story.series_id != series_id
        if series_id is not None:
            _get(db, series_id)
            if any(b.series_number == number and b.id != story_id for b in _books(db, series_id)):
                raise ValueError(SERIES_NUMBER_TAKEN.format(number=number))
        update = {'series_id': series_id, 'series_number': number, 'series_start': start, 'revision': story.revision + 1}
        if series_id is None or entering:
            update['series_start_version_id'] = None
        story = story.model_copy(update=update)
        repo._save_story(db, story)
    if entering and number and number > 1:
        return take_snapshot_if_ready(repo, story.id)
    return story


def take_snapshot_if_ready(repo, story_id: str) -> Story:
    """Placeholder until the start snapshot (Task 3): returns the story unchanged."""
    return repo.get_story(story_id)
