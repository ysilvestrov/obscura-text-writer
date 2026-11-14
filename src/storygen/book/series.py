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
        stories = repo.list_stories(include_trashed=True)
        status = replace(status, prequel=is_prequel(_series_books(stories, story), story))
    return status


def _snapshot_status(repo, story) -> SeriesStatus | None:
    from ..characters.models import load_characters
    from ..memory.series_start import read_series_start
    if not story.series_id:
        return None
    source = source_book(repo.list_stories(include_trashed=True), story)
    snapshot = None
    if story.series_start_version_id:
        snapshot = read_series_start(repo.read_text(story.series_start_version_id), story.series_start_version_id).source
    if source is None:
        return SeriesStatus('source_changed' if snapshot else 'first')
    view = repo.context_view(source.id)
    summary, _ = book_summary(view, view.story)
    found = SeriesStatus('no_summary', source.id, source.series_number)
    if snapshot is None:
        return found if summary is None else SeriesStatus('source_finished', source.id, source.series_number)
    cards = load_characters(view.read_text(source.characters_version_id)) if source.characters_version_id else []
    hashes = snapshot.get('source_card_hashes', {})
    changed = [c.id for c in cards if c.id in hashes and hashes[c.id] != card_hash(c)]
    same = (snapshot.get('source_story_id') == source.id and snapshot.get('source_summary_version_id') == summary
            and snapshot.get('source_characters_version_id') == source.characters_version_id)
    return SeriesStatus('fresh' if same and not changed else 'source_changed', source.id, source.series_number, changed)


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
