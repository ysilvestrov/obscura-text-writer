"""MEMORY-ENTITIES overlay: the effective participants and locations of a memory record (no IO)."""
from dataclasses import dataclass, replace
from typing import Literal, Mapping

from ..domain import MemoryEntityMark
from ..locations import canonical
from .projection import MemoryItem

Source = Literal['event', 'model', 'author']
_WEAKNESS = {'author': 3, 'model': 2, 'event': 1}


@dataclass(frozen=True)
class Effective:
    participant_ids: tuple[str, ...]
    location_ids: tuple[str, ...]
    participants_from: Source | None
    locations_from: Source | None

    @property
    def source(self) -> Source | None:
        """The least reliable contributor that influenced the record: author, else model, else event, else None."""
        found = {s for s in (self.participants_from, self.locations_from) if s}
        return max(found, key=_WEAKNESS.__getitem__) if found else None


def _unique(ids):
    return tuple(dict.fromkeys(ids))


def effective(category: str, participant_ids, location_ids, mark: MemoryEntityMark | None,
        known_cards: frozenset[str], merged: Mapping[str, str | None]) -> Effective:
    def pick(event_ids, mark_ids, clean):
        if mark and mark.source == 'author':
            return clean(mark_ids), 'author'
        for ids, source in ((event_ids, 'event'), (mark_ids if mark else (), 'model')):
            ids = clean(ids)
            if ids:
                return ids, source
        return (), None

    people, people_from = ((), None) if category == 'character_states' else pick(
        participant_ids, mark.participant_ids if mark else (), lambda ids: _unique(i for i in ids if i in known_cards))
    places, places_from = pick(
        location_ids, mark.location_ids if mark else (), lambda ids: _unique(canonical(merged, i) for i in ids))
    return Effective(people, places, people_from, places_from)


@dataclass(frozen=True)
class EntityResolver:
    marks: Mapping[str, MemoryEntityMark]
    known_cards: frozenset[str]
    merged: Mapping[str, str | None]

    def of(self, claim_id, category, participant_ids, location_ids) -> Effective:
        return effective(category, participant_ids, location_ids, self.marks.get(claim_id), self.known_cards, self.merged)

    def item(self, item: MemoryItem) -> MemoryItem:
        category = 'character_states' if item.section == 'core' else item.section
        e = self.of(item.claim_id, category, item.participant_ids, item.location_ids)
        return replace(item, participant_ids=e.participant_ids, location_ids=e.location_ids)

    def items(self, items) -> tuple[MemoryItem, ...]:
        return tuple(self.item(i) for i in items)

    def bare(self) -> 'EntityResolver':
        return EntityResolver({}, self.known_cards, self.merged)
