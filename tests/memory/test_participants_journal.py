"""MEMORY-ENTITIES-S01: participant_ids of memory records in the journal."""
import json

import pytest

from storygen.memory.journal import MemoryJournal, _add_event, _change_event, _extend, normalize_manual_memory, replay_memory
from tests.memory.test_wire_v4 import MOOD, PROSE, T1


@pytest.mark.req('MEMORY-ENTITIES')
def test_empty_participants_are_not_serialized():
    e = _add_event('facts', 'Маяк згас', 'p1', 'цитата', 0)
    assert 'participant_ids' not in json.loads(e.model_dump_json())
    with_ids = _add_event('facts', 'Маяк згас', 'p1', 'цитата', 0, participant_ids=['c1'])
    assert json.loads(with_ids.model_dump_json())['participant_ids'] == ['c1']


@pytest.mark.req('MEMORY-ENTITIES')
def test_participants_do_not_change_claim_id():
    a = _add_event('facts', 'Маяк згас', 'p1', 'цитата', 0)
    b = _add_event('facts', 'Маяк згас', 'p1', 'цитата', 0, participant_ids=['c1'])
    assert a.claim_id == b.claim_id and a.event_id == b.event_id


@pytest.mark.req('MEMORY-ENTITIES')
def test_participants_on_a_state_are_rejected():
    with pytest.raises(ValueError, match='Учасники дозволені лише для ліній, фактів і хронології'):
        MemoryJournal(schema_version=4, source_prose_ids=['p1'],
                      events=[_add_event('character_states', 'Оля втомлена', 'p1', 'ц', 0, ['c1'], participant_ids=['c2'])])


@pytest.mark.req('MEMORY-ENTITIES')
@pytest.mark.parametrize('ids', [['c1', 'c1'], [' ']])
def test_duplicate_or_blank_participants_are_rejected(ids):
    event = _add_event('facts', 'Маяк згас', 'p1', 'ц', 0, participant_ids=ids)
    with pytest.raises(ValueError, match='Некоректні учасники пам’яті'):
        replay_memory(MemoryJournal.model_construct(schema_version=4, source_prose_ids=['p1'], events=[event]))


@pytest.mark.req('MEMORY-ENTITIES')
def test_a_change_must_keep_the_participants_of_its_claim():
    add = _add_event('open_threads', 'Хто стукав?', 'p1', 'q', 0, participant_ids=['c1'])
    kept = _change_event('update', add.claim_id, 'Хто стукав вночі?', 'open_threads', [], 'p2', 'r', participant_ids=['c1'])
    assert replay_memory(MemoryJournal(schema_version=4, source_prose_ids=['p1', 'p2'], events=[add, kept]))[add.claim_id].participant_ids == ['c1']
    moved = _change_event('update', add.claim_id, 'Хто стукав вночі?', 'open_threads', [], 'p2', 'r', participant_ids=['c2'])
    with pytest.raises(ValueError, match='Не можна змінювати учасників claim'):
        MemoryJournal(schema_version=4, source_prose_ids=['p1', 'p2'], events=[add, moved])


@pytest.mark.req('MEMORY-ENTITIES')
def test_journal_with_participants_is_v4_and_never_goes_back():
    placed = _add_event('facts', 'Ключ у кишені', 'p1', 'q', 0, location_ids=['loc_kitchen'])
    v3 = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=[placed])
    with_ids = _add_event('facts', 'Лист на столі', 'p2', 'r', 0, participant_ids=['c1'])
    v4 = _extend(v3, 'p2', [with_ids])
    assert v4.schema_version == 4
    more = _add_event('facts', 'Двері відчинені', 'p3', 's', 0, location_ids=['loc_house'])
    assert _extend(v4, 'p3', [more]).schema_version == 4
    plain = _add_event('facts', 'Тиша', 'p3', 't', 0)
    assert _extend(v3, 'p3', [plain]).schema_version == 3


@pytest.mark.req('MEMORY-ENTITIES')
def test_manual_change_without_participants_inherits_them():
    add = _add_event('open_threads', 'Хто стукав?', 'p1', 'Хто стукав?', 0, participant_ids=['c1'])
    prev = MemoryJournal(schema_version=4, source_prose_ids=['p1'], events=[add])
    retire = _change_event('retire', add.claim_id, 'Стукав сусід', 'open_threads', [], 'p2', 'Надворі ніч.')  # no participants given
    raw = json.dumps({'schema_version': 4, 'source_prose_ids': ['p1', 'p2'],
                      'events': [json.loads(e.model_dump_json()) for e in (add, retire)]}, ensure_ascii=False)
    assert 'participant_ids' not in json.loads(raw)['events'][1]
    journal = normalize_manual_memory(raw, prev, 'p2', PROSE, ['h'])
    assert journal.events[1].operation == 'retire' and journal.events[1].participant_ids == ['c1']
    assert journal.schema_version == 4


@pytest.mark.req('MEMORY-ENTITIES')
def test_manual_save_keeps_the_participants_of_a_new_record():
    prev = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=[MOOD])
    add = _add_event('facts', 'Лист на столі', 'p2', 'Лист на столі.', 0, participant_ids=['c1'])
    raw = json.dumps({'schema_version': 4, 'source_prose_ids': ['p1', 'p2'],
                      'events': [json.loads(e.model_dump_json()) for e in (MOOD, add)]}, ensure_ascii=False)
    journal = normalize_manual_memory(raw, prev, 'p2', PROSE, ['h'])
    assert journal.events[1].participant_ids == ['c1'] and journal.schema_version == 4


@pytest.mark.req('MEMORY-ENTITIES')
def test_thread_resolution_keeps_participants():
    from types import SimpleNamespace
    from storygen.memory.core_review import ThreadEdit, _author_events
    thread = T1.model_copy(update={'participant_ids': ['c1']})
    base = MemoryJournal(schema_version=4, source_prose_ids=['p1'], events=[thread])
    ctx = SimpleNamespace(prose_id='p2', sources={'p2': 'Стукав сусід.'})
    edit = ThreadEdit(kind='thread', claim_id=thread.claim_id, action='close', text='Стукав сусід', quote='Стукав сусід.')
    retire, fact = _author_events(base, [edit], ctx, {'p2'})
    assert retire.participant_ids == ['c1'] and fact.participant_ids == ['c1']


@pytest.mark.req('MEMORY-ENTITIES')
def test_merge_keeps_participants():
    from storygen.memory.merge import Conflict, MergePlan, _author_events as merge_events
    thread = T1.model_copy(update={'participant_ids': ['c1']})
    base = MemoryJournal(schema_version=4, source_prose_ids=['p1'], events=[thread])
    plan = MergePlan(base, [], [], 4)
    conflict = Conflict(key='claim:' + thread.claim_id, values={}, events={'h1': [thread]})
    assert merge_events(plan, conflict, 'Інше питання', 'merge-1', {})[0].participant_ids == ['c1']
    new = _add_event('facts', 'Лист', 'p1', 'q', 0, participant_ids=['c2'])
    blank = MergePlan(MemoryJournal(source_prose_ids=['p1']), [], [], 2)
    conflict = Conflict(key='claim:none', values={}, events={'h1': [new]})
    assert merge_events(blank, conflict, 'Лист', 'merge-1', {})[0].participant_ids == ['c2']


@pytest.mark.req('MEMORY-ENTITIES')
def test_a_journal_below_v4_rejects_participants():
    event = _add_event('facts', 'Маяк згас', 'p1', 'ц', 0, participant_ids=['c1'])
    for version in (2, 3):
        with pytest.raises(ValueError, match='Учасники пам’яті потребують журналу версії 4'):
            MemoryJournal(schema_version=version, source_prose_ids=['p1'], events=[event])
    assert MemoryJournal(schema_version=4, source_prose_ids=['p1'], events=[event]).schema_version == 4


@pytest.mark.req('MEMORY-ENTITIES')
def test_merge_result_is_v4_with_participants_and_v4_plan_stays_v4():
    from storygen.memory.journal import _extend
    from storygen.memory.merge import build_merged_journal, plan_merge
    base = _extend(MemoryJournal(), 'p0', [_add_event('facts', 'Місто на річці', 'p0', 'q', 0)])
    plain = _extend(base, 'p1', [_add_event('facts', 'Лист', 'p1', 'q1', 0)])
    withp = _extend(base, 'p2', [_add_event('facts', 'Ключ', 'p2', 'q2', 0, participant_ids=['c1'])])
    sources = ['p0', 'p1', 'p2']
    merged = build_merged_journal(plan_merge({'h1': plain, 'h2': withp}, ['h1', 'h2']), {}, sources, 'm')
    assert merged.schema_version == 4
    v4_plain = MemoryJournal(schema_version=4, source_prose_ids=['p0', 'p1'], events=plain.events)
    again = build_merged_journal(plan_merge({'h1': v4_plain}, ['h1']), {}, ['p0', 'p1'], 'm')
    assert again.schema_version == 4
