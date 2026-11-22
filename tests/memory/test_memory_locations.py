"""MEMORY-LOCATIONS-S04: location_ids of memory records in the journal and in wire v4."""
import json

import pytest

from storygen.memory.journal import (MemoryEvent, MemoryJournal, _add_event, _change_event, normalize_manual_memory,
    replay_memory)
from storygen.memory.wire_v4 import check_v4, memory_wire_v4_schema, schema_bounds_v4
from tests.memory.test_wire_v4 import (BOUNDS, PREV, PROSE, MOOD, T1, answer, bad, chg, core, dec, new, padd, run, sadd,
    tdec, threads)

pytestmark = pytest.mark.req('MEMORY-LOCATIONS')

KITCHEN, HOUSE, FOREST = 'loc_kitchen', 'loc_house', 'loc_forest'
LBOUNDS = schema_bounds_v4(PREV, PROSE, ['h'], ['h'], {'h': False}, location_ids=[KITCHEN, HOUSE])


def located(item, *ids):
    return {**item, 'location_ids': list(ids)}


def test_empty_location_ids_are_not_serialized_and_old_journals_read():
    event = _add_event('facts', 'Ключ у кишені', 'p1', 'q', 0)
    assert 'location_ids' not in json.loads(event.model_dump_json())
    placed = _add_event('facts', 'Ключ у кишені', 'p1', 'q', 0, location_ids=[KITCHEN])
    assert json.loads(placed.model_dump_json())['location_ids'] == [KITCHEN]
    assert placed.claim_id == event.claim_id  # the place is no part of the claim identity
    assert MemoryEvent.model_validate_json(event.model_dump_json()).location_ids == []


def test_a_change_keeps_the_location_of_its_claim_and_replay_rejects_another():
    state = _add_event('character_states', 'Втомлена', 'p1', 'q', 0, ['h'], location_ids=[KITCHEN])
    update = _change_event('update', state.claim_id, 'Сердита', state.category, state.character_ids, 'p2', 'r',
                           location_ids=state.location_ids)
    journal = MemoryJournal(schema_version=3, source_prose_ids=['p1', 'p2'], events=[state, update])
    assert replay_memory(journal)[state.claim_id].location_ids == [KITCHEN]
    moved = update.model_copy(update={'location_ids': [FOREST]})
    with pytest.raises(ValueError):
        replay_memory(MemoryJournal(schema_version=3, source_prose_ids=['p1', 'p2'], events=[state, moved]))


def test_bounds_and_schema_list_locations_only_when_the_scene_has_some():
    assert 'location_ids' not in BOUNDS
    assert LBOUNDS['location_ids'] == [KITCHEN, HOUSE]
    plain = memory_wire_v4_schema(BOUNDS)
    assert 'location_ids' not in json.dumps(plain)
    schema = memory_wire_v4_schema(LBOUNDS)['properties']
    for category in ('facts', 'character_states', 'open_threads', 'timeline'):
        item = schema[category]['properties']['add']['items']['properties']
        assert item['location_ids'] == {'type': 'array', 'items': {'type': 'string', 'enum': [KITCHEN, HOUSE]}}


def test_wire_v4_adds_carry_allowed_locations():
    data = answer(facts_add=[located(padd('Лист на столі', ['f000005']), KITCHEN)],
                  character_states_add=[located(sadd('Змерзла', ['f000004'], ['h']), HOUSE)])
    journal = run(data, bounds=LBOUNDS)
    assert {e.text: e.location_ids for e in new(journal)} == {'Лист на столі': [KITCHEN], 'Змерзла': [HOUSE]}


def test_an_answer_without_location_ids_is_accepted_for_a_scene_with_locations():
    journal = run(answer(facts_add=[padd('Лист на столі', ['f000005'])]), bounds=LBOUNDS)
    assert new(journal)[0].location_ids == []


def test_unknown_or_repeated_location_is_a_violation():
    assert ('facts.add[0]', 'location_unknown') in bad(answer(facts_add=[located(padd('Лист', ['f000005']), FOREST)]), bounds=LBOUNDS)
    assert ('facts.add[0]', 'location_unknown') in bad(answer(facts_add=[located(padd('Лист', ['f000005']), KITCHEN, KITCHEN)]), bounds=LBOUNDS)
    assert ('facts.add[0]', 'location_unknown') in bad(answer(facts_add=[located(padd('Лист', ['f000005']), KITCHEN)]))


def test_wire_changes_inherit_the_claim_location():
    placed = MOOD.model_copy(update={'location_ids': [KITCHEN]})
    prev = PREV.model_copy(update={'events': [placed if e.claim_id == MOOD.claim_id else e for e in PREV.events]})
    bounds = schema_bounds_v4(prev, PROSE, ['h'], ['h'], {'h': False}, location_ids=[KITCHEN])
    data = answer(character_states_update=[chg(MOOD.claim_id, 'Ніч', ['f000004'])])
    journal = run(data, prev=prev, bounds=bounds)
    assert replay_memory(journal)[MOOD.claim_id].location_ids == [KITCHEN]


def test_closing_a_thread_keeps_its_location_on_the_retire():
    placed = T1.model_copy(update={'location_ids': [HOUSE]})
    prev = PREV.model_copy(update={'events': [placed if e.claim_id == T1.claim_id else e for e in PREV.events]})
    bounds = schema_bounds_v4(prev, PROSE, ['h'], ['h'], {'h': False})
    data = answer(threads_=threads(**{T1.claim_id: tdec('closed', 'Стукав сусід', ['f000003'])}))
    journal = run(data, prev=prev, bounds=bounds)
    retire = next(e for e in new(journal, prev) if e.operation == 'retire')
    assert retire.location_ids == [HOUSE]


def test_manual_save_keeps_new_locations_and_fills_changes_from_their_claim():
    placed = MOOD.model_copy(update={'location_ids': [KITCHEN]})
    prev = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=[placed])
    add = _add_event('facts', 'Лист на столі', 'p2', 'Лист на столі.', 0, location_ids=[HOUSE])
    update = _change_event('update', MOOD.claim_id, 'Ніч', MOOD.category, ['h'], 'p2', 'Надворі ніч.')  # no location given
    raw = json.dumps({'schema_version': 3, 'source_prose_ids': ['p1', 'p2'],
                      'events': [json.loads(e.model_dump_json()) for e in (placed, add, update)]}, ensure_ascii=False)
    journal = normalize_manual_memory(raw, prev, 'p2', PROSE, ['h'])
    events = journal.events[1:]
    assert events[0].location_ids == [HOUSE] and events[1].location_ids == [KITCHEN]


def test_author_merge_of_arcs_keeps_the_record_location():
    from storygen.memory.merge import Conflict, MergePlan, _author_events
    placed = MOOD.model_copy(update={'location_ids': [KITCHEN]})
    base = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=[placed])
    plan = MergePlan(base, [], [], 3)
    conflict = Conflict(key='claim:' + MOOD.claim_id, values={}, events={'h1': [placed]})
    events = _author_events(plan, conflict, 'Спокійна', 'merge-1', {})
    assert events[0].operation == 'update' and events[0].location_ids == [KITCHEN]
