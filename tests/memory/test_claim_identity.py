"""MEMORY-003-S09: the claim ID names the scene, not its prose version."""
import json
import pytest
from storygen.evidence import fragment_text
from storygen.memory.carry import carry_journal
from storygen.memory.journal import MemoryJournal, _add_event, apply_operations, normalize_manual_memory

P1A = 'Олена тримає валізу.\n\nНадворі дощ.'
P1B = 'Олена тримає валізу.\n\nНадворі злива.'  # a change outside the quoted fragment
P2 = 'Олена ставить валізу на підлогу.'


def fid(text, index=0):
    return fragment_text(text)[index].id


def first(prose_id, prose, scene_id='s1'):
    return apply_operations(MemoryJournal(), {'operations': [{'action': 'add', 'category': 'character_states',
        'text': 'Олена тримає валізу.', 'character_ids': ['c1'], 'evidence_id': fid(prose)}]}, prose_id, prose, ['c1'],
        scene_id=scene_id)


@pytest.mark.req('MEMORY-003')
def test_claim_id_names_the_scene_not_the_prose_version():
    a = _add_event('facts', 'Т', 'p1', 'ц', 0, scene_id='s1')
    assert a.claim_id == _add_event('facts', 'Т', 'p2', 'ц', 0, scene_id='s1').claim_id
    assert a.claim_id != _add_event('facts', 'Т', 'p1', 'ц', 0, scene_id='s2').claim_id
    # Without a scene (benchmark replay, legacy conversion) the v2 form stays.
    assert a.claim_id != _add_event('facts', 'Т', 'p1', 'ц', 0).claim_id


@pytest.mark.req('MEMORY-003')
def test_new_prose_with_the_same_claims_carries_later_updates():
    old, new = first('p1a', P1A), first('p1b', P1B)
    assert old.events[0].claim_id == new.events[0].claim_id
    claim = old.events[0].claim_id
    later = apply_operations(old, {'operations': [{'action': 'update', 'category': 'character_states', 'claim_id': claim,
        'text': 'Олена поставила валізу.', 'character_ids': ['c1'], 'evidence_id': fid(P2)}]}, 'p2', P2, ['c1'], scene_id='s2')
    carried = carry_journal(new, later)
    assert carried.source_prose_ids == ['p1b', 'p2']


@pytest.mark.req('MEMORY-003')
def test_manual_resave_keeps_v2_ids_of_older_claims():
    prose = 'Олена тримає валізу.\n\nНадворі дощ.'
    older = apply_operations(MemoryJournal(), {'operations': [
        {'action': 'add', 'category': 'facts', 'text': 'Валіза важка.', 'evidence_id': fid(prose)},
        {'action': 'add', 'category': 'facts', 'text': 'Іде дощ.', 'evidence_id': fid(prose, 1)}]}, 'p1', prose, [])
    data = json.loads(older.model_dump_json())
    data['events'][1]['text'] = 'Іде сильний дощ.'
    saved = normalize_manual_memory(json.dumps(data, ensure_ascii=False), MemoryJournal(), 'p1', prose, [], scene_id='s1')
    assert saved.events[0].claim_id == older.events[0].claim_id
    assert saved.events[1].claim_id == _add_event('facts', 'Іде сильний дощ.', 'p1', 'Надворі дощ.', 0, scene_id='s1').claim_id
