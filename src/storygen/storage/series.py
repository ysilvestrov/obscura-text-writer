"""SERIES storage: the series table (CAS on its revision) and the series fields of a book (CAS on the story revision)."""
import json

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


NO_SOURCE = 'Попередня книга ще не має підсумку'
CARD_NAME_CLASH = 'Картки з тими самими іменами вже є в книзі: {names}'


def _source(repo, story):
    from ..book.series import book_summary, source_book
    source = source_book(repo.list_stories(include_trashed=True), story)
    if source is None:
        return None, None, None
    view = repo.context_view(source.id)
    summary, _ = book_summary(view, view.story)
    return source, view, summary


def _copy_cards(repo, story, view, source):
    """Copy the source cards into the book: same card and entry IDs, «from scene» entries become timeless, citations move
    onto a new source_characters version of the book. Returns (cards version id or None, card hashes)."""
    from ..book.series import card_hash
    from ..characters.models import load_characters
    from ..scene_description import name_key
    if not source.characters_version_id:
        return story.characters_version_id, {}
    cards = load_characters(view.read_text(source.characters_version_id))
    own = load_characters(repo.read_text(story.characters_version_id)) if story.characters_version_id else []
    own_ids = {c.id for c in own}
    by_name = {name_key(c.name): c for c in own}
    clash = [c.name for c in cards if name_key(c.name) in by_name and by_name[name_key(c.name)].id != c.id]
    if clash:
        raise ValueError(CARD_NAME_CLASH.format(names=', '.join(clash)))
    hashes = {c.id: card_hash(c) for c in cards}
    added = [c for c in cards if c.id not in own_ids]
    if not added:
        return story.characters_version_id, hashes
    quotes = list(dict.fromkeys(s.quote for c in added for e in c.entries for s in e.sources))
    text_id = repo.save_version(story.id, None, 'source_characters', '\n'.join(quotes), []).id if quotes else None
    copied = []
    for c in added:
        entries = []
        for e in c.entries:
            entry = json.loads(e.model_dump_json())
            if entry['availability'] == 'from_scene':
                entry['availability'], entry['available_from_scene_id'] = 'timeless', None
            entry['sources'] = [{**s, 'version_id': text_id} for s in entry['sources']]
            entries.append(entry)
        copied.append({**json.loads(c.model_dump_json()), 'entries': entries})
    merged = [json.loads(c.model_dump_json()) for c in own] + copied
    load_characters(json.dumps(merged, ensure_ascii=False))
    saved = repo.save_version(story.id, None, 'character_cards', json.dumps(merged, ensure_ascii=False), [text_id] if text_id else [])
    repo.publish_story_material(story.id, 'characters_version_id', saved.id, repo.get_story(story.id).revision)
    return saved.id, hashes


def take_snapshot(repo, story_id: str, expected_revision: int) -> Story:
    """Take (or retake) the start snapshot: the summary journal of the source book as scene 0 and a copy of its cards."""
    from ..book.series import summary_journal
    from ..memory.series_start import inherit_journal, series_start_payload
    story = repo.get_story(story_id)
    if story.revision != expected_revision:
        raise RevisionConflict(STORY_CONFLICT)
    source, view, summary = _source(repo, story)
    if not summary:
        raise ValueError(NO_SOURCE)
    journal, texts = summary_journal(view, summary)
    text, inherited = inherit_journal(journal, texts)
    cards_id, hashes = _copy_cards(repo, story, view, source)
    summary_ref = view.get_version(summary)
    cards_ref = view.get_version(source.characters_version_id) if source.characters_version_id else None
    payload = series_start_payload(text, inherited, {
        'source_story_id': source.id, 'source_summary_version_id': summary, 'source_summary_sha256': summary_ref.sha256,
        'source_characters_version_id': cards_ref.id if cards_ref else None,
        'source_characters_sha256': cards_ref.sha256 if cards_ref else None,
        'source_card_hashes': hashes, 'characters_version_id': cards_id})
    start = repo.save_version(story.id, None, 'series_start', payload, [cards_id] if cards_id else [])
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = repo._active_story(db, story_id)
        current = current.model_copy(update={'series_start_version_id': start.id, 'revision': current.revision + 1})
        repo._save_story(db, current)
    return current


def take_snapshot_if_ready(repo, story_id: str) -> Story:
    """On entering a series: take the snapshot when the source book has a summary and no card clashes; otherwise leave
    the book without one (its status explains why)."""
    story = repo.get_story(story_id)
    try:
        return take_snapshot(repo, story_id, story.revision)
    except ValueError:
        return repo.get_story(story_id)


def create_book(repo, series_id: str, title: str) -> Story:
    """«Нова книга серії»: a new story with the next free number; the snapshot follows when the source has a summary."""
    from ..domain import StoryCreate
    books = series_books(repo, series_id)
    number = max((b.series_number or 0 for b in books), default=0) + 1
    story = repo.create_story(StoryCreate(title=title))
    return set_story_series(repo, story.id, series_id, number, None, story.revision)
