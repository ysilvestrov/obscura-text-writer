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
CARD_SKIPPED = 'Не додано картки, однойменні з картками книги: {names}'
CARD_CHANGED = 'Картки змінилися в попередній книзі й не перезаписані: {names}'


def _copy_cards(repo, story, view, source, refuse=True):
    """Copy the source cards into the book: same card and entry IDs, «from scene» entries become timeless, citations move
    onto a new source_characters version of the book. Cards already in the book by ID stay as they are; a card with the
    name of a book card under another ID refuses the copy (`refuse`) or is skipped and named (a refresh). Returns
    (cards version id or None, names skipped)."""
    from ..characters.models import load_characters
    from ..scene_description import name_key
    if not source.characters_version_id:
        return story.characters_version_id, []
    cards = load_characters(view.read_text(source.characters_version_id))
    own = load_characters(repo.read_text(story.characters_version_id)) if story.characters_version_id else []
    own_ids = {c.id for c in own}
    by_name = {name_key(c.name): c for c in own}
    clash = [c.name for c in cards if c.id not in own_ids and name_key(c.name) in by_name]
    if clash and refuse:
        raise ValueError(CARD_NAME_CLASH.format(names=', '.join(clash)))
    added = [c for c in cards if c.id not in own_ids and name_key(c.name) not in by_name]
    if not added:
        return story.characters_version_id, clash
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
    return saved.id, clash


def take_snapshot(repo, story_id: str, expected_revision: int) -> Story:
    """Take (or retake) the start snapshot: the start memory of the book (the summary journal of the main book merged
    with the prequels between, SERIES-S08) as scene 0 and a copy of the sources' cards."""
    return _snapshot(repo, story_id, expected_revision, refuse=True)[0]


def refresh_snapshot(repo, story_id: str, expected_revision: int) -> tuple[Story, list[str]]:
    """«Оновити з попередньої книги»: a new snapshot from the current summary of the source. Cards: those missing by ID
    and by name are added; same-name cards under another ID and cards changed in the source since the last snapshot are
    named in the warnings, never overwritten. Without a snapshot it is the first snapshot."""
    from ..characters.models import load_characters
    from ..book.series import card_hash
    from ..memory.series_start import read_series_start
    story = repo.get_story(story_id)
    if not story.series_start_version_id:
        return take_snapshot(repo, story_id, expected_revision), []
    old = read_series_start(repo.read_text(story.series_start_version_id), story.series_start_version_id).source
    old_hashes = {item['story_id']: item['card_hashes'] for item in old['sources']}
    story, clash, sources = _snapshot(repo, story_id, expected_revision, refuse=False)
    warnings = [CARD_SKIPPED.format(names=', '.join(clash))] if clash else []
    changed = []
    for item in sources:
        hashes = old_hashes.get(item['story_id'], {})
        if item['characters_version_id']:
            changed += [c.name for c in load_characters(repo.read_text(item['characters_version_id']))
                        if c.id in hashes and hashes[c.id] != card_hash(c) and c.name not in changed]
    if changed:
        warnings.append(CARD_CHANGED.format(names=', '.join(changed)))
    return story, warnings


def _snapshot(repo, story_id, expected_revision, refuse):
    from ..book.series import start_memory
    from ..memory.series_start import inherit_journal, series_start_payload
    story = repo.get_story(story_id)
    if story.revision != expected_revision:
        raise RevisionConflict(STORY_CONFLICT)
    memory = start_memory(repo, story)
    if memory is None or memory.missing is not None:
        raise ValueError(NO_SOURCE)
    text, inherited = inherit_journal(memory.journal, memory.texts)
    cards_id, clash = story.characters_version_id, []
    for item in memory.sources:
        source = repo.get_story(item['story_id'])
        cards_id, skipped = _copy_cards(repo, repo.get_story(story_id), repo.context_view(source.id), source, refuse)
        clash += [name for name in skipped if name not in clash]
    payload = series_start_payload(text, inherited, {'sources': memory.sources, 'resolved': memory.resolved,
                                                     'characters_version_id': cards_id})
    start = repo.save_version(story.id, None, 'series_start', payload, [cards_id] if cards_id else [])
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current = repo._active_story(db, story_id)
        current = current.model_copy(update={'series_start_version_id': start.id, 'revision': current.revision + 1})
        repo._save_story(db, current)
    return current, clash, memory.sources


def take_snapshot_if_ready(repo, story_id: str) -> Story:
    """On entering a series: take the snapshot when the source book has a summary and no card clashes; otherwise leave
    the book without one (its status explains why)."""
    story = repo.get_story(story_id)
    try:
        return take_snapshot(repo, story_id, story.revision)
    except ValueError:
        return repo.get_story(story_id)


SERIES_LINES_INVALID = 'Рядки «Серія:», «Номер:» і «Початок:» не розпізнано; книгу не додано до серії.'
SERIES_CREATED = 'Створено нову серію «{title}»'


def enter_series_from_plan(repo, story_id: str, lines, invalid: bool) -> list[str]:
    """The plan preamble: find the series by title (or create it) and put the book in with its number and start. A
    taken number or unparsed lines give a warning and leave the book's series fields as they are."""
    if invalid:
        return [SERIES_LINES_INVALID]
    if lines is None:
        return []
    item = find_series(repo, lines.title)
    if item and any(b.series_number == lines.number and b.id != story_id for b in series_books(repo, item.id)):
        return [SERIES_NUMBER_TAKEN.format(number=lines.number) + '; книгу не додано до серії.']
    notes = []
    try:
        if item is None:
            item = create_series(repo, lines.title)
            notes.append(SERIES_CREATED.format(title=item.title))
        set_story_series(repo, story_id, item.id, lines.number, lines.start, repo.get_story(story_id).revision)
    except ValueError as error:
        return notes + [str(error)]
    return notes


def create_book(repo, series_id: str, title: str) -> Story:
    """«Нова книга серії»: a new story with the next free number; the snapshot follows when the source has a summary."""
    from ..domain import StoryCreate
    books = series_books(repo, series_id)
    number = max((b.series_number or 0 for b in books), default=0) + 1
    story = repo.create_story(StoryCreate(title=title))
    return set_story_series(repo, story.id, series_id, number, None, story.revision)
