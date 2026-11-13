"""MEMORY-MERGE: three-way merge of arc memory journals with author decisions. Pure, no IO.

Every head journal is the shared base plus events of its own branch (a scene journal always extends its predecessor's).
A key is a record (`claim:<id>`, records without a slot) or a core slot (`slot:<character>:<slot>`). A key changed in one
branch merges as is; a key changed in several branches with the same final value takes the events of the first branch in
reading order; different final values are a conflict that only an author decision resolves: the events of one branch, or
one author event (`source_kind='author'`, no quote) citing the prose of the latest head.
"""
from dataclasses import dataclass, field

from .journal import MemoryEvent, MemoryJournal, _add_event, _change_event, _nonstandard, replay_memory

AUTHOR = 'author'


@dataclass
class Conflict:
    key: str
    values: dict[str, str | None]
    events: dict[str, list[MemoryEvent]]
    # (branch index, index in branch, event) of every head, for ordering the chosen events.
    entries: dict[str, list[tuple[int, int, MemoryEvent]]] = field(default_factory=dict, repr=False, compare=False)


@dataclass
class MergePlan:
    base: MemoryJournal
    clean: list[tuple[int, int, MemoryEvent]]
    conflicts: list[Conflict]
    schema_version: int = 2

    @property
    def clean_events(self) -> list[MemoryEvent]:
        return [event for _, _, event in self.clean]


def shared_base(branches: dict[str, MemoryJournal], order: list[str]) -> MemoryJournal:
    """Events whose sources every head shares; they must be the same prefix of every head journal."""
    common = set.intersection(*(set(branches[h].source_prose_ids) for h in order))
    first = branches[order[0]]
    sources = [s for s in first.source_prose_ids if s in common]
    events = [e for e in first.events if e.source_version_id in common]
    for head in order:
        journal = branches[head]
        if journal.events[:len(events)] != events or any(e.source_version_id in common for e in journal.events[len(events):]):
            raise ValueError(f'Пам’ять голови {head} спирається на іншу історію; оновіть пам’ять цієї арки')
    return MemoryJournal(schema_version=max(branches[h].schema_version for h in order), source_prose_ids=sources,
                         events=[e.model_copy(deep=True) for e in events])


def _key(event: MemoryEvent) -> str:
    return f'slot:{event.character_ids[0]}:{event.slot}' if event.slot else f'claim:{event.claim_id}'


def _value(active: dict[str, MemoryEvent], key: str) -> str | None:
    if key.startswith('slot:'):
        _, character, slot = key.split(':', 2)
        record = next((e for e in active.values() if e.slot == slot and e.character_ids[:1] == [character]), None)
        return record.text if record else None
    record = active.get(key[len('claim:'):])
    return record.text if record else None


def plan_merge(branches: dict[str, MemoryJournal], order: list[str]) -> MergePlan:
    """`order`: head IDs in reading order. Raises ValueError when the head journals do not share one base."""
    base = shared_base(branches, order)
    touched: dict[str, dict[str, list[tuple[int, int, MemoryEvent]]]] = {}
    finals = {}
    for b, head in enumerate(order):
        journal = branches[head]
        finals[head] = replay_memory(journal)
        for i, event in enumerate(journal.events[len(base.events):]):
            touched.setdefault(_key(event), {}).setdefault(head, []).append((b, i, event))
    clean, conflicts = [], []
    for key, by_head in touched.items():
        heads = [h for h in order if h in by_head]
        values = {h: _value(finals[h], key) for h in heads}
        if len(heads) > 1 and len(set(values.values())) > 1:
            conflicts.append(Conflict(key, values, {h: [e for _, _, e in by_head[h]] for h in heads}, by_head))
        else:
            clean.extend(by_head[heads[0]])
    return MergePlan(base, clean, conflicts, max(j.schema_version for j in branches.values()))


def _author_events(plan: MergePlan, conflict: Conflict, text: str, source_id: str, duplicates: dict) -> list[MemoryEvent]:
    base_active = replay_memory(plan.base)
    kwargs = dict(source_kind=AUTHOR)
    if conflict.key.startswith('slot:'):
        _, character, slot = conflict.key.split(':', 2)
        record = next((e for e in base_active.values() if e.slot == slot and e.character_ids[:1] == [character]), None)
        category, characters = 'character_states', [character]
    else:
        record = base_active.get(conflict.key[len('claim:'):])
        slot = None
        sample = next(e for events in conflict.events.values() for e in events)
        category, characters = (record.category, record.character_ids) if record else (sample.category, sample.character_ids)
    if record is not None:
        if text:
            return [_change_event('update', record.claim_id, text, record.category, record.character_ids, source_id, None, slot=slot, **kwargs)]
        return [_change_event('retire', record.claim_id, record.text, record.category, record.character_ids, source_id, None, slot=slot, **kwargs)]
    if not text:
        return []
    duplicate = (category, text)
    occurrence = duplicates.get(duplicate, 0)
    duplicates[duplicate] = occurrence + 1
    return [_add_event(category, text, source_id, None, occurrence, characters, slot=slot, **kwargs)]


def _failing_key(base_count: int, journal_args: dict, events: list[MemoryEvent]) -> str:
    for n in range(base_count + 1, len(events) + 1):
        try:
            replay_memory(MemoryJournal.model_construct(**journal_args, events=events[:n]))
        except ValueError:
            return _key(events[n - 1])
    return ''


def build_merged_journal(plan: MergePlan, decisions: dict[str, dict], source_prose_ids: list[str], author_source_id: str) -> MemoryJournal:
    """The merged journal: base, chosen events in reading order of their sources, then author events."""
    positions = {source: i for i, source in enumerate(source_prose_ids)}
    chosen = list(plan.clean)
    authored, duplicates = [], {}
    for conflict in plan.conflicts:
        decision = decisions.get(conflict.key)
        if not decision:
            raise ValueError(f'Бракує рішення для конфлікту {conflict.key}')
        choice = decision.get('choice')
        if choice == AUTHOR:
            authored.extend(_author_events(plan, conflict, (decision.get('text') or '').strip(), author_source_id, duplicates))
        elif choice in conflict.entries:
            chosen.extend(conflict.entries[choice])
        else:
            raise ValueError(f'Невідомий вибір для конфлікту {conflict.key}')
    try:
        ordered = sorted(chosen, key=lambda item: (positions[item[2].source_version_id], item[0], item[1]))
    except KeyError as exc:
        raise ValueError(f'Подія злиття посилається на джерело поза злиттям: {exc.args[0]}') from None
    events = [e.model_copy(deep=True) for e in plan.base.events] + [e for _, _, e in ordered] + authored
    schema = 3 if plan.schema_version == 3 or any(_nonstandard(e) for e in events) else 2
    args = dict(schema_version=schema, source_prose_ids=list(source_prose_ids))
    try:
        return MemoryJournal(**args, events=events)
    except ValueError as exc:
        key = _failing_key(len(plan.base.events), args, events)
        raise ValueError(f'Злитий журнал не відтворюється ({key or "невідомий ключ"}): {exc}') from None


def carry_decisions(old_conflicts: list[dict], old_decisions: dict, conflicts: list[Conflict]) -> dict:
    """Decisions of an earlier merge for conflicts with the same key and the same value of every head."""
    old = {item['key']: item['values'] for item in old_conflicts}
    return {c.key: old_decisions[c.key] for c in conflicts
            if c.key in old_decisions and old.get(c.key) == c.values}
