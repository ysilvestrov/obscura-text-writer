"""MEMORY-ENTITIES-S01: participant_ids in wire v4 bounds, schema, check and the translated journal."""
import json

import pytest

from storygen.memory.journal import MemoryJournal, _add_event, replay_memory
from storygen.memory.wire_v4 import MemoryWireV4, check_v4, memory_wire_v4_schema, schema_bounds_v4, wire_v4_events
from tests.memory.test_wire_v4 import (BOUNDS, PREV, PROSE, MOOD, T1, T2, answer, bad, chg, new, padd, run, sadd, tdec,
    threads)

PBOUNDS = schema_bounds_v4(PREV, PROSE, ['h'], ['h'], {'h': False}, participant_ids=['c1', 'c2'])


def with_members(item, *ids):
    return {**item, 'participant_ids': list(ids)}


@pytest.mark.req('MEMORY-ENTITIES')
def test_bounds_without_cards_are_byte_for_byte_the_same():
    plain = schema_bounds_v4(PREV, PROSE, ['h'], ['h'], {'h': False})
    assert plain == schema_bounds_v4(PREV, PROSE, ['h'], ['h'], {'h': False}, participant_ids=())
    assert 'participant_ids' not in plain
    assert 'participant_ids' not in json.dumps(memory_wire_v4_schema(plain))
    assert PBOUNDS['participant_ids'] == ['c1', 'c2']


@pytest.mark.req('MEMORY-ENTITIES')
def test_schema_requires_participants_in_facts_threads_and_timeline_adds_only():
    schema = memory_wire_v4_schema(PBOUNDS)['properties']
    for category in ('facts', 'open_threads', 'timeline'):
        item = schema[category]['properties']['add']['items']
        assert item['properties']['participant_ids']['items']['enum'] == ['c1', 'c2']
        assert 'participant_ids' in item['required']
    assert 'participant_ids' not in schema['character_states']['properties']['add']['items']['properties']


@pytest.mark.req('MEMORY-ENTITIES')
def test_unknown_or_repeated_participant_is_refused():
    for ids in (['zz'], ['c1', 'c1']):
        data = answer(facts_add=[with_members(padd('Лист', ['f000005']), *ids)])
        assert ('facts.add[0]', 'participant_unknown') in bad(data, bounds=PBOUNDS)
    # without cards any participant is unknown
    assert ('timeline.add[0]', 'participant_unknown') in bad(answer(timeline_add=[with_members(padd('Лист', ['f000005']), 'c1')]))


@pytest.mark.req('MEMORY-ENTITIES')
def test_old_answer_without_participants_is_valid():
    assert check_v4(answer(facts_add=[padd('Лист', ['f000005'])]), PREV, PBOUNDS) == []
    assert check_v4(answer(facts_add=[padd('Лист', ['f000005'])]), PREV, BOUNDS) == []


@pytest.mark.req('MEMORY-ENTITIES')
def test_translated_journal_keeps_participants_and_is_v4():
    data = answer(facts_add=[with_members(padd('Лист на столі', ['f000005']), 'c2')],
                  threads_=threads(**{T1.claim_id: tdec('closed', 'Стукав сусід', ['f000003'])}))
    journal = run(data, bounds=PBOUNDS)
    assert journal.schema_version == 4
    assert [e.participant_ids for e in new(journal) if e.text == 'Лист на столі'] == [['c2']]
    # a journal without participants stays v3
    assert run(answer(facts_add=[padd('Лист', ['f000005'])])).schema_version == 3


@pytest.mark.req('MEMORY-ENTITIES')
def test_closing_a_thread_gives_the_resolution_fact_the_participants_of_the_thread():
    thread = _add_event('open_threads', 'Хто стукав?', 'p1', 'Перша сцена.', 0, participant_ids=['c1'])
    prev = MemoryJournal(schema_version=4, source_prose_ids=['p1'], events=[e if e.claim_id != T1.claim_id else thread for e in PREV.events])
    bounds = schema_bounds_v4(prev, PROSE, ['h'], ['h'], {'h': False}, participant_ids=['c1'])
    data = answer(threads_=threads(**{thread.claim_id: tdec('closed', 'Стукав сусід', ['f000003'])}))
    journal = run(data, prev=prev, bounds=bounds)
    retire, fact = new(journal, prev)
    assert (retire.operation, retire.participant_ids) == ('retire', ['c1'])
    assert (fact.category, fact.participant_ids) == ('facts', ['c1'])
    assert thread.claim_id not in replay_memory(journal)


@pytest.mark.req('MEMORY-ENTITIES')
def test_states_never_get_participants():
    from storygen.memory.core import SLOTS
    from tests.memory.test_wire_v4 import CLOTH, core, dec
    data = answer(core(clothing=dec('unknown', reason='Новий день')),
                  character_states_add=[sadd('Змерзла', ['f000004'], ['h'])])
    journal = run(data, bounds=PBOUNDS)
    assert all(e.participant_ids == [] for e in new(journal) if e.category == 'character_states')
    assert SLOTS
