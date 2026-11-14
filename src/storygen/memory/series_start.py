"""SERIES: the start snapshot of a book in a series is scene 0 of its memory.

A `series_start` version (story-level, no scene) holds the summary journal of the previous book with every source and
evidence reference moved onto the snapshot itself, and a text with every quote of that journal, so the records keep
their kind, quotes, slots and IDs and pass the usual quote check. The stored journal names its source with a marker:
the version ID is known only after `save_version`, so reading replaces the marker with it.
"""
import json
from dataclasses import dataclass, field

from .journal import MemoryJournal

SERIES_MARKER = 'series:start'
SERIES_START_SCHEMA = 1
SERIES_START_KIND = 'series_start'


@dataclass(frozen=True)
class SeriesStartData:
    text: str
    journal: MemoryJournal
    source: dict
    decisions: dict | None = None  # a prequel (SERIES-S09): {key: 'past' | 'future'}; None — every record is past
    future: list = field(default_factory=list)  # [{key, category, text, character_ids, story_id}] of the future keys


def inherit_journal(journal: MemoryJournal, texts: dict[str, str]) -> tuple[str, MemoryJournal]:
    """The snapshot text (every quote and supporting quote, one block per line, no repeats, in event order) and the
    journal with source and evidence references moved onto the marker. `texts` are the source texts of `journal`."""
    blocks = []
    for event in journal.events:
        source = texts[event.evidence_version_id or event.source_version_id]
        for quote in [event.quote, *event.supporting_quotes]:
            if quote is None:
                continue
            if quote not in source:
                raise ValueError('Запис підсумку не має дослівного підтвердження у джерелі')
            if quote not in blocks:
                blocks.append(quote)
    events = [e.model_copy(update={'source_version_id': SERIES_MARKER,
                                   'evidence_version_id': SERIES_MARKER if e.evidence_version_id is not None else None})
              for e in journal.events]
    inherited = MemoryJournal(schema_version=journal.schema_version, source_prose_ids=[SERIES_MARKER], events=events)
    return '\n'.join(blocks), inherited


def series_start_payload(text: str, journal: MemoryJournal, source: dict) -> str:
    return json.dumps({'schema_version': SERIES_START_SCHEMA, **source, 'text': text,
                       'journal': json.loads(journal.model_dump_json())}, ensure_ascii=False)


def read_series_start(raw: str, version_id: str) -> SeriesStartData:
    data = json.loads(raw)
    if data.get('schema_version') != SERIES_START_SCHEMA:
        raise ValueError('Непідтримувана версія знімка серії')
    journal = MemoryJournal.model_validate(data['journal'])
    if journal.source_prose_ids != [SERIES_MARKER]:
        raise ValueError('Знімок серії має інше джерело')

    def own(value):
        return version_id if value == SERIES_MARKER else value
    events = [e.model_copy(update={'source_version_id': own(e.source_version_id),
                                   'evidence_version_id': own(e.evidence_version_id)}) for e in journal.events]
    resolved = MemoryJournal(schema_version=journal.schema_version, source_prose_ids=[version_id], events=events)
    source = {k: v for k, v in data.items() if k not in {'schema_version', 'text', 'journal'}}
    if 'sources' not in source:  # a 4a snapshot: one source in single fields
        source['sources'] = [{
            'story_id': source.get('source_story_id'), 'summary_version_id': source.get('source_summary_version_id'),
            'summary_sha256': source.get('source_summary_sha256'),
            'characters_version_id': source.get('source_characters_version_id'),
            'characters_sha256': source.get('source_characters_sha256'),
            'card_hashes': source.get('source_card_hashes') or {}}] if source.get('source_story_id') else []
    source.setdefault('resolved', [])
    return SeriesStartData(data['text'], resolved, source, data.get('decisions'), data.get('future', []))


def prequel_split(text: str, journal: MemoryJournal, decisions: dict[str, str], origins: dict[str, str]):
    """A prequel's snapshot from its whole start memory (`text` and `journal` with the marker as source): the journal
    keeps the events of the `past` keys, the text only their quotes; the active records of the other keys are the
    future. Returns (text, journal, future)."""
    from .journal import replay_memory
    from .merge import _key
    past = [e for e in journal.events if decisions.get(_key(e)) == 'past']
    kept = MemoryJournal(schema_version=journal.schema_version, source_prose_ids=[SERIES_MARKER], events=past)
    kept_text, kept = inherit_journal(kept, {SERIES_MARKER: text})
    future = [{'key': _key(e), 'category': e.category, 'text': e.text, 'character_ids': list(e.character_ids),
               'story_id': origins.get(_key(e))}
              for e in replay_memory(journal).values() if decisions.get(_key(e)) != 'past']
    return kept_text, kept, future


def source_number(version_ref, numbers: dict[str, int]) -> int:
    """Scene number of a memory source: 0 for the start snapshot of a series book, else the number of its scene."""
    return 0 if version_ref.kind == SERIES_START_KIND else numbers[version_ref.scene_id]


def scene_series_start(story, scenes, scene) -> str | None:
    """The start snapshot a scene extends: the book's snapshot for a scene without ancestors in the book, else None
    (a scene with ancestors reaches it through their memory)."""
    from ..book.lineage import previous_scenes
    if not story.series_start_version_id or previous_scenes(story, scenes, scene):
        return None
    return story.series_start_version_id


def read_source(reader, version_id: str, ref=None) -> str:
    """Text of a memory source: the prose itself, or the quote text of a start snapshot."""
    ref = ref or reader.get_version(version_id)
    raw = reader.read_text(version_id)
    return read_series_start(raw, version_id).text if ref.kind == SERIES_START_KIND else raw
