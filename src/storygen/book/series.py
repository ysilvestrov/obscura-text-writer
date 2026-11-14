"""SERIES: the source book of a snapshot and the summary of a book. Read-only."""
import hashlib
from dataclasses import dataclass, field, replace
import json

SUMMARY_NEEDS_MERGE = 'потрібне злиття кінця книги'
SUMMARY_NO_MEMORY = 'остання сцена без актуальної пам’яті'


def source_book(stories, story):
    """The book of the same series, not in the trash, with the greatest number below the book's number; None for the
    first book or a book outside a series."""
    if not story.series_id or not story.series_number:
        return None
    earlier = [s for s in stories if s.series_id == story.series_id and not s.trashed_at and s.id != story.id
               and s.series_number and s.series_number < story.series_number]
    return max(earlier, key=lambda s: s.series_number, default=None)


def book_summary(view, story) -> tuple[str | None, str | None]:
    """(version id, reason): the usable book-end merge when the book ends in two or more heads, else the fresh memory of
    the last active scene. Scenes without prose are active too, so a book not written to its end has no summary."""
    from ..book.lineage import book_end_heads
    from ..storage.memory_merges import merge_point, usable_merge
    scenes = view.list_scenes(story.id)
    active = [s for s in scenes if not s.trashed_at]
    if not active:
        return None, SUMMARY_NO_MEMORY
    heads = book_end_heads(story, active)
    if len(heads) >= 2:
        merged = usable_merge(view, story, active, merge_point(story, active, book_end=True))
        return (merged, None) if merged else (None, SUMMARY_NEEDS_MERGE)
    end = next(s for s in active if s.id == heads[0])  # the scene the book ends in: its own memory, not a predecessor's
    memory_id = end.heads.get('memory')
    if not memory_id:
        return None, SUMMARY_NO_MEMORY
    ref = view.get_version(memory_id)
    if not ref.complete or view.is_stale(memory_id):
        return None, SUMMARY_NO_MEMORY
    return memory_id, None


def summary_journal(view, version_id):
    """The journal of a summary (a scene memory or the journal inside a book-end merge) and the texts of its sources;
    a series start source (book 3 from book 2) gives its quote text."""
    from ..memory.journal import MemoryJournal, load_memory
    from ..memory.series_start import SERIES_START_KIND, read_series_start
    ref = view.get_version(version_id)
    raw = view.read_text(version_id)
    journal = MemoryJournal.model_validate(json.loads(raw)['journal']) if ref.kind == 'memory_merge' else load_memory(raw)
    texts = {}
    for id in journal.source_prose_ids:
        source = view.get_version(id)
        text = view.read_text(id)
        texts[id] = read_series_start(text, id).text if source.kind == SERIES_START_KIND else text
    return journal, texts


def card_hash(card) -> str:
    return hashlib.sha256(card.model_dump_json().encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class SeriesStatus:
    """The start snapshot of a series book against its source, computed on read and never stored. `state`: 'first'
    (no source book), 'no_summary' (no snapshot, the source has no summary), 'source_finished' (no snapshot, the
    source has a summary now), 'source_changed' (the summary, the cards or the source book differ from the
    snapshot), 'fresh'."""
    state: str
    source_story_id: str | None = None
    source_number: int | None = None
    changed_cards: list = field(default_factory=list)
    prequel: bool = False  # earlier on the axis than a book with a smaller number (SERIES-001, 4b)
    resolved: list = field(default_factory=list)  # conflicts the automatic merge of the start memory settled


@dataclass
class StartMemory:
    """The start memory of a series book (SERIES-S08): the merged summary journal of its sources and the texts of the
    journal's sources. `sources[i] = {story_id, summary_version_id, summary_sha256, characters_version_id,
    characters_sha256, card_hashes}`; `resolved[i] = {key, kept_story_id, dropped: [{story_id, text}]}`; `missing` is
    the first source without a summary (then the journal is None)."""
    journal: object
    texts: dict
    sources: list
    resolved: list
    missing: object = None
    origins: dict = field(default_factory=dict)  # merge key -> the source book whose events the record came from


def _source_rows(repo, story):
    """(sources with their views and summaries, the first source without a summary or None)."""
    from ..characters.models import load_characters
    rows = []
    for book in start_sources(repo.list_stories(include_trashed=True), story):
        view = repo.context_view(book.id)
        summary, _ = book_summary(view, view.story)
        if summary is None:
            return rows, book
        cards = load_characters(view.read_text(book.characters_version_id)) if book.characters_version_id else []
        cards_ref = view.get_version(book.characters_version_id) if book.characters_version_id else None
        rows.append((book, view, {
            'story_id': book.id, 'summary_version_id': summary, 'summary_sha256': view.get_version(summary).sha256,
            'characters_version_id': book.characters_version_id, 'characters_sha256': cards_ref.sha256 if cards_ref else None,
            'card_hashes': {c.id: card_hash(c) for c in cards}}))
    return rows, None


def start_memory(repo, story) -> StartMemory | None:
    """The sources of the book's start (`start_sources`) and their merged summary journals: one source is taken as is
    (4a); several merge automatically, a conflict keeps the events of the main book when it is involved, otherwise of the
    source latest in the chronology (no moment or a tie: the greater number). None when the book has no sources."""
    from ..memory.merge import plan_merge, build_merged_journal
    rows, missing = _source_rows(repo, story)
    from ..memory.merge import _key
    if missing is not None:
        return StartMemory(None, {}, [row for _, _, row in rows], [], missing)
    if not rows:
        return None
    journals, texts, owners = {}, {}, {}
    for book, view, row in rows:
        journals[book.id], own = summary_journal(view, row['summary_version_id'])
        texts.update(own)
        for id in journals[book.id].source_prose_ids:
            owners.setdefault(id, book.id)
    sources = [row for _, _, row in rows]

    def origins(journal):
        return {_key(e): owners[e.source_version_id] for e in journal.events}
    if len(rows) == 1:
        return StartMemory(journals[rows[0][0].id], texts, sources, [], origins=origins(journals[rows[0][0].id]))
    order = [book.id for book, _, _ in rows]
    main = rows[0][0] if not is_prequel(_series_books(repo.list_stories(include_trashed=True), story), rows[0][0]) else None
    moments = chronology_moments([b for b in repo.list_stories(include_trashed=True)
                                  if b.series_id == story.series_id and b.series_number and not b.trashed_at])
    numbers = {book.id: book.series_number for book, _, _ in rows}
    plan = plan_merge(journals, order)
    decisions, resolved = {}, []
    for conflict in plan.conflicts:
        heads = list(conflict.values)
        winner = main.id if main and main.id in heads else max(
            heads, key=lambda id: (id in moments, moments.get(id, (0, 0, 0)), numbers[id]))
        decisions[conflict.key] = {'choice': winner}
        resolved.append({'key': conflict.key, 'kept_story_id': winner,
                         'dropped': [{'story_id': id, 'text': conflict.values[id]} for id in heads if id != winner]})
    prose_ids = list(dict.fromkeys(id for head in order for id in journals[head].source_prose_ids))
    merged = build_merged_journal(plan, decisions, prose_ids, prose_ids[-1])
    return StartMemory(merged, texts, sources, resolved, origins=origins(merged))


def _series_books(stories, story):
    return [s for s in stories if s.series_id == story.series_id and s.series_number]


def prequel_ids(books) -> set[str]:
    """Books not in the trash on the chronology axis whose moment is earlier than the moment of some book not in the
    trash with a smaller number. A book off the axis is not a prequel."""
    live = [b for b in books if not b.trashed_at]
    moments = chronology_moments(live)
    by_id = {b.id: b for b in live}
    return {id for id, moment in moments.items()
            if any(other != id and by_id[other].series_number < by_id[id].series_number and moments[other] > moment
                   for other in moments)}


def is_prequel(books, story) -> bool:
    return story.id in prequel_ids(books)


def start_sources(stories, story) -> list:
    """The sources of a book's start memory: the main book (the nearest earlier book not in the trash that is not a
    prequel) and the prequels not in the trash between it and the book, by number; [] outside a series or for the first
    book. Without a main book, every earlier prequel."""
    if not story.series_id or not story.series_number:
        return []
    books = _series_books(stories, story)
    prequels = prequel_ids(books)
    earlier = sorted((b for b in books if not b.trashed_at and b.id != story.id and b.series_number < story.series_number),
                     key=lambda b: b.series_number)
    main = next((b for b in reversed(earlier) if b.id not in prequels), None)
    floor = main.series_number if main else 0
    return ([main] if main else []) + [b for b in earlier if b.id in prequels and b.series_number > floor]


def series_status(repo, story) -> SeriesStatus | None:
    status = _snapshot_status(repo, story)
    if status is not None:
        from ..memory.series_start import read_series_start
        stories = repo.list_stories(include_trashed=True)
        prequel = is_prequel(_series_books(stories, story), story)
        status = replace(status, prequel=prequel)
        if prequel and status.state == 'fresh' and read_series_start(
                repo.read_text(story.series_start_version_id), story.series_start_version_id).decisions is None:
            status = replace(status, state='prequel_review')  # a 4a snapshot: every record is past until reviewed
    return status


def _snapshot_status(repo, story) -> SeriesStatus | None:
    """The snapshot against the current sources: their set, summaries and cards (SERIES-S08)."""
    from ..memory.series_start import read_series_start
    if not story.series_id:
        return None
    snapshot = None
    if story.series_start_version_id:
        snapshot = read_series_start(repo.read_text(story.series_start_version_id), story.series_start_version_id).source
    books = start_sources(repo.list_stories(include_trashed=True), story)
    if not books:
        return SeriesStatus('source_changed' if snapshot else 'first')
    rows, missing = _source_rows(repo, story)
    lead = missing or books[0]
    if snapshot is None:
        return SeriesStatus('no_summary' if missing else 'source_finished', lead.id, lead.series_number)
    if missing:
        return SeriesStatus('source_changed', lead.id, lead.series_number)
    old = {item['story_id']: item for item in snapshot['sources']}
    changed = [id for _, _, row in rows for id, value in row['card_hashes'].items()
               if row['story_id'] in old and id in old[row['story_id']]['card_hashes']
               and old[row['story_id']]['card_hashes'][id] != value]
    key = ('story_id', 'summary_version_id', 'characters_version_id')
    same = [[item.get(k) for k in key] for item in snapshot['sources']] == [[row[k] for k in key] for _, _, row in rows]
    return SeriesStatus('fresh' if same and not changed else 'source_changed', lead.id, lead.series_number,
                        list(dict.fromkeys(changed)), resolved=snapshot['resolved'])


def chronology(books) -> tuple[list[str], list[str]]:
    """The series axis by `Початок` (SERIES-001): (placed ids by moment and number, outside ids in release order)."""
    ordered = sorted(books, key=lambda item: item.series_number or 0)
    moments = chronology_moments(books)
    placed = sorted(moments, key=lambda id: (moments[id], next(b.series_number for b in ordered if b.id == id)))
    return placed, [item.id for item in ordered if item.id not in placed]


def chronology_moments(books) -> dict[str, tuple[int, int, int]]:
    """Moments of the books on the axis: the first book without a start (by number) is the origin; a start is a time mark
    counted from its anchor, which must be an earlier book of the series already on the axis, so there are no cycles.
    Every other book (a second book without start, a later, missing or off-axis anchor, an offset that is not a time
    mark) is off the axis."""
    from ..memory.story_time import _relative
    ordered = sorted(books, key=lambda item: item.series_number or 0)
    origin = next((item for item in ordered if not item.series_start), None)
    moments = {}
    if origin is not None:
        moments[origin.series_number] = (0, 0, 0)
        for item in ordered:
            if item is origin or not item.series_start:
                continue
            moment = _relative(item.series_start.offset)
            base = moments.get(item.series_start.anchor)
            if moment is None or base is None or item.series_start.anchor >= (item.series_number or 0):
                continue
            moments[item.series_number] = tuple(a + b for a, b in zip(base, moment.key))
    return {item.id: moments[item.series_number] for item in ordered if item.series_number in moments}
