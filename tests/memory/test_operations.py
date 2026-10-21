import pytest
from storygen.memory.models import MemorySnapshot, MemoryEntry


def operation(action='add',category='character_states',text='A у бібліотеки',target=None,characters=None,evidence='f000001'):
    from storygen.memory.journal import MemoryOperation
    return MemoryOperation(action=action,category=category,text=text,claim_id=target,
        character_ids=characters or [],evidence_id=evidence)


def test_state_updates_and_retires_keep_proof_history():
    from storygen.memory.journal import MemoryJournal,MemoryOperations,apply_operations,replay_memory
    one=apply_operations(MemoryJournal(),MemoryOperations(operations=[operation(characters=['A'])]),'p1','A у бібліотеки.',['A'])
    claim=one.events[0].claim_id
    two=apply_operations(one,MemoryOperations(operations=[operation('update',text='A вийшов',target=claim,characters=['A'])]),'p2','A вийшов.',['A'])
    assert replay_memory(two)[claim].text=='A вийшов'
    three=apply_operations(two,MemoryOperations(operations=[operation('retire',text='A завершив візит',target=claim,characters=['A'])]),'p3','Візит завершено.',['A'])
    assert not replay_memory(three)
    assert three.events[:2]==two.events and len(three.events)==3
    assert len({e.claim_id for e in three.events})==1
    assert [e.source_version_id for e in three.events]==['p1','p2','p3']


@pytest.mark.parametrize('change',[{'target':'unknown'}, {'category':'facts'}, {'characters':['B']}, {'evidence':'f999999'}])
def test_bad_change_rejects_whole_batch_without_mutating_previous(change):
    from storygen.memory.journal import MemoryJournal,MemoryOperations,apply_operations
    one=apply_operations(MemoryJournal(),MemoryOperations(operations=[operation(characters=['A'])]),'p1','Доказ',['A'])
    before=one.model_dump_json()
    values={'target':one.events[0].claim_id,'characters':['A']};values.update(change)
    with pytest.raises(ValueError):
        apply_operations(one,MemoryOperations(operations=[operation(category='timeline'),operation('update',**values)]),'p2','Доказ',['A'])
    assert one.model_dump_json()==before


def test_protocol_limits_and_duplicate_targets():
    from storygen.memory.journal import MemoryOperations
    with pytest.raises(ValueError):MemoryOperations(operations=[operation() for _ in range(4)])
    with pytest.raises(ValueError):MemoryOperations(operations=[operation('update',target='id') for _ in range(2)])
    with pytest.raises(ValueError):MemoryOperations(operations=[operation('update',target=str(i)) for i in range(13)])


def test_legacy_snapshot_preserves_retired_events():
    from storygen.memory.journal import MemoryJournal,MemoryOperations,apply_operations,legacy_view,merge_legacy_snapshot
    first=apply_operations(MemoryJournal(),MemoryOperations(operations=[operation(category='open_threads')]),'p1','Питання відкрите',[])
    second=apply_operations(first,MemoryOperations(operations=[operation('retire',category='open_threads',text='Завершено',target=first.events[0].claim_id)]),'p2','Питання закрите',[])
    snapshot=legacy_view(second);snapshot.source_prose_ids.append('p3')
    snapshot.timeline.append(MemoryEntry(text='Новий день',source_version_id='p3',quote='Ранок'))
    result=merge_legacy_snapshot(second,snapshot,'p3','Ранок почався')
    assert result.events[:2]==second.events and result.events[-1].text=='Новий день'
    assert result.source_prose_ids==['p1','p2','p3']


def test_invalid_v2_never_falls_back_to_legacy_delta():
    from storygen.memory.journal import parse_memory_result,MemoryJournal
    with pytest.raises(ValueError):parse_memory_result('{"schema_version":2,"facts":[]}',MemoryJournal(),'p','Текст','evidence_delta',[])


def test_duplicate_json_fields_and_whitespace_proof_are_rejected():
    from storygen.memory.journal import parse_memory_result,MemoryJournal,MemoryEvent
    with pytest.raises(ValueError):
        parse_memory_result('{"schema_version":2,"operations":[],"operations":[]}',MemoryJournal(),'p','Текст','evidence_delta',[])
    with pytest.raises(ValueError):
        MemoryEvent(event_id='e',claim_id='c',operation='add',category='facts',text='Факт',source_version_id='p',quote=' ')
