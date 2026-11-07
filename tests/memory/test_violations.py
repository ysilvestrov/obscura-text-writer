import json
import pytest
from storygen.evidence import fragment_text
from storygen.memory.journal import MemoryJournal, MemoryOperation, MemoryOperations, apply_operations, parse_memory_result
from storygen.memory.violations import Violation, MemoryViolations, check_v2, pydantic_violations


def add(category,ev='f000001',**kw):
    kw.setdefault('text','Claim')
    return dict(action='add',category=category,evidence_id=ev,**kw)


def upd(claim,category='character_states',action='update',**kw):
    kw.setdefault('character_ids',['A'] if category=='character_states' else [])
    return dict(action=action,category=category,claim_id=claim,text='Claim',evidence_id='f000001',**kw)


PREV=apply_operations(MemoryJournal(),MemoryOperations(operations=[
    MemoryOperation(action='add',category='character_states',text='A тут',character_ids=['A'],evidence_id='f000001'),
    MemoryOperation(action='add',category='facts',text='Факт',evidence_id='f000001')]),'p1','Доказ.',['A'])
STATE_ID,FACT_ID=PREV.events[0].claim_id,PREV.events[1].claim_id
FRAGS={f.id for f in fragment_text('Доказ.')}
ALLOWED=['A']


def codes(data):
    return [(v.operation,v.code) for v in check_v2(data,PREV,FRAGS,ALLOWED)]


def test_v2_collects_independent_violations():
    data={'schema_version':2,'operations':[
        add('facts',ev='f000001,f000002'),
        add('facts'),add('facts'),add('facts'),
        upd(STATE_ID,category='open_threads'),
        upd(STATE_ID)]}
    found=codes(data)
    assert ('operations[0]','evidence_unknown') in found
    assert ('operations[4]','target_meta') in found
    assert ('$','add_limit') in found and ('$','target_twice') in found


def test_v2_missing_evidence_is_schema_for_that_operation():
    bad=add('facts');del bad['evidence_id']
    found=codes({'schema_version':2,'operations':[bad,add('facts',ev='nope'),upd(STATE_ID,category='open_threads')]})
    assert found==[('operations[0]','schema'),('operations[1]','evidence_unknown'),('operations[2]','target_meta')]


def test_v2_fact_target_is_target_unknown():
    assert codes({'schema_version':2,'operations':[upd(FACT_ID,category='facts')]})==[('operations[0]','target_unknown')]
    assert codes({'schema_version':2,'operations':[upd('mc_missing')]})==[('operations[0]','target_unknown')]


def test_v2_scope_and_envelope_and_ops_limit():
    assert codes({'schema_version':2,'operations':[add('character_states',character_ids=['B'])]})==[('operations[0]','scope_unknown')]
    for bad in ([],{'schema_version':3,'operations':[]},{'schema_version':2,'operations':{}},{'schema_version':2,'operations':[],'x':1}):
        assert codes(bad)==[('$','schema')]
    assert ('$','ops_limit') in codes({'schema_version':2,'operations':[add('timeline') for _ in range(13)]})
    assert codes({'schema_version':2,'operations':['text']})==[('operations[0]','schema')]
    assert codes({'schema_version':2,'operations':[add('timeline')]})==[]


def test_pydantic_violations_label_and_dedupe():
    with pytest.raises(Exception) as caught:
        MemoryOperation.model_validate({'action':'x','category':'y'})
    found=pydantic_violations(caught.value,lambda loc:'character_states.add[0]')
    assert found==[Violation('character_states.add[0]','schema')]


def test_payload_caps_at_50_and_keeps_total():
    payload=MemoryViolations([Violation(f'operations[{i}]','schema') for i in range(60)]).payload()
    assert len(payload['items'])==50 and payload['total']==60
    assert payload['items'][0]=={'operation':'operations[0]','code':'schema'}


def test_memory_error_shows_count_and_first_three_without_values():
    from storygen.memory.diagnostics import memory_error
    msg=memory_error(MemoryViolations([Violation(f'operations[{i}]','schema') for i in range(5)]))
    assert msg.startswith('5 порушень') and msg.count(';')==2 and 'f000' not in msg
    assert 'Операція 1' in msg and 'Операція 4' not in msg
    assert memory_error(MemoryViolations([Violation('$','add_limit')])).startswith('1 порушення: Відповідь')
    assert memory_error(MemoryViolations([Violation('$','schema')]*2)).startswith('2 порушення')
    assert memory_error(MemoryViolations([Violation('$','schema')]*12)).startswith('12 порушень')


def test_parse_memory_result_raises_all_violations_without_values():
    raw=json.dumps({'schema_version':2,'operations':[add('facts',ev='secret-evidence')]+[add('timeline',text='private text') for _ in range(4)]})
    with pytest.raises(MemoryViolations) as caught:
        parse_memory_result(raw,PREV,'p2','Доказ.','evidence_delta',['A'])
    assert [(v.operation,v.code) for v in caught.value.violations]==[('operations[0]','evidence_unknown'),('$','add_limit')]
    assert 'private' not in str(caught.value) and 'secret' not in str(caught.value)
