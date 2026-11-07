import json
import pytest
from storygen.memory.journal import MemoryJournal, MemoryOperation, MemoryOperations, apply_operations, parse_memory_result, replay_memory
from storygen.memory.violations import MemoryViolations, Violation

PROSE_1='Доказ.'
PROSE='Рядок один.\nРядок два.\nРядок три.\nРядок чотири.\nРядок п’ять.'
PREV=apply_operations(MemoryJournal(),MemoryOperations(operations=[
    MemoryOperation(action='add',category='character_states',text='C1 тут',character_ids=['c1'],evidence_id='f000001'),
    MemoryOperation(action='add',category='open_threads',text='Лінія',evidence_id='f000001'),
    MemoryOperation(action='add',category='facts',text='Факт',evidence_id='f000001')]),'p1',PROSE_1,['c1'])
STATE_ID,THREAD_ID,FACT_ID=(e.claim_id for e in PREV.events)
FRAG={f'f00000{i}':line for i,line in enumerate(PROSE.split('\n'),1)}


def sadd(text,ids,chars=()):return {'text':text,'evidence_ids':ids,'character_ids':list(chars)}
def padd(text,ids):return {'text':text,'evidence_ids':ids}
def chg(claim,text,ids):return {'claim_id':claim,'text':text,'evidence_ids':ids}


def v3(facts_add=(),states_add=(),states_update=(),states_retire=(),threads_add=(),threads_update=(),threads_retire=(),timeline_add=()):
    return json.dumps({'schema_version':3,'facts':{'add':list(facts_add)},
        'character_states':{'add':list(states_add),'update':list(states_update),'retire':list(states_retire)},
        'open_threads':{'add':list(threads_add),'update':list(threads_update),'retire':list(threads_retire)},
        'timeline':{'add':list(timeline_add)}})


def run(raw,chars=('c1',),**kw):
    return parse_memory_result(raw,PREV,'p2',PROSE,'evidence_delta',list(chars),wire_version=3,**kw)


def violations(raw,**kw):
    with pytest.raises(MemoryViolations) as e:run(raw,**kw)
    return [tuple(v) for v in e.value.violations]


def test_v3_translates_to_v2_journal_with_stable_ids():
    raw=v3(states_add=[sadd('Т',['f000002'],['c1'])],threads_update=[chg(THREAD_ID,'Нове',['f000003'])])
    j=run(raw)
    v2_ops=[dict(action='add',category='character_states',text='Т',character_ids=['c1'],evidence_id='f000002'),
            dict(action='update',category='open_threads',claim_id=THREAD_ID,text='Нове',evidence_id='f000003')]
    v2=parse_memory_result(json.dumps({'schema_version':2,'operations':v2_ops}),PREV,'p2',PROSE,'evidence_delta',['c1'])
    assert j==v2 and j.source_prose_ids==['p1','p2']


def test_v3_update_takes_category_and_scope_from_catalog():
    j=run(v3(states_update=[chg(STATE_ID,'Новий стан',['f000001'])]))
    event=j.events[-1]
    assert (event.category,event.character_ids,event.claim_id,event.operation)==('character_states',['c1'],STATE_ID,'update')


def test_v3_multiple_evidence_become_supporting_quotes():
    j=run(v3(facts_add=[padd('Ф',['f000001','f000005','f000003'])],threads_retire=[chg(THREAD_ID,'Кін',['f000002','f000004'])]))
    fact,retire=j.events[-2:]
    assert fact.quote==FRAG['f000001'] and fact.supporting_quotes==[FRAG['f000005'],FRAG['f000003']]
    assert retire.operation=='retire' and retire.supporting_quotes==[FRAG['f000004']]
    assert replay_memory(j).get(THREAD_ID) is None


def test_v3_violations():
    four=[padd(f'Ф{i}',['f000001']) for i in range(4)]
    assert violations(v3(facts_add=four))==[('facts.add','add_limit')]
    assert violations(v3(facts_add=[padd('Ф',[])]))==[('facts.add[0]','evidence_count')]
    assert violations(v3(facts_add=[padd('Ф',['f000001','f000002','f000003','f000004'])]))==[('facts.add[0]','evidence_count')]
    assert violations(v3(facts_add=[padd('Ф',['f000001','f000001'])]))==[('facts.add[0]','evidence_count')]
    assert violations(v3(timeline_add=[padd('Ф',['f000009'])]))==[('timeline.add[0]','evidence_unknown')]
    assert violations(v3(states_add=[sadd('Ф',['f000001'],['zzz'])]))==[('character_states.add[0]','scope_unknown')]
    many=dict(facts_add=[padd(f'a{i}',['f000001']) for i in range(3)],timeline_add=[padd(f'b{i}',['f000001']) for i in range(3)],
        threads_add=[padd(f'c{i}',['f000001']) for i in range(3)],states_add=[sadd(f'd{i}',['f000001']) for i in range(3)])
    assert violations(v3(**many,threads_update=[chg(THREAD_ID,'x',['f000001'])]))==[('$','ops_limit')]


def test_v3_same_claim_update_and_retire_is_target_twice():
    raw=v3(states_update=[chg(STATE_ID,'a',['f000001'])],states_retire=[chg(STATE_ID,'b',['f000001'])])
    assert violations(raw)==[('$','target_twice')]


def test_v3_claim_from_other_category_is_target_unknown():
    assert violations(v3(threads_update=[chg(STATE_ID,'a',['f000001'])]))==[('open_threads.update[0]','target_unknown')]
    assert violations(v3(states_retire=[chg('mc_unknown','a',['f000001'])]))==[('character_states.retire[0]','target_unknown')]


def test_v3_fact_claim_cannot_be_targeted():
    data=json.loads(v3());data['facts']['update']=[chg(FACT_ID,'a',['f000001'])]
    assert violations(json.dumps(data))==[('facts.update','schema')]


def test_v3_schema_does_not_echo_model_keys_and_rejects_extra_character_ids():
    data=json.loads(v3());data['секрет']=1;data['facts']['add']=[{'text':'Ф','evidence_ids':['f000001'],'character_ids':[]}]
    assert violations(json.dumps(data))==[('facts.add[0]','schema'),('$','schema')]


def test_v3_empty_response_records_prose():
    j=run(v3())
    assert j.source_prose_ids==['p1','p2'] and len(j.events)==len(PREV.events)


def test_wire_version_mismatch():
    v2_raw=json.dumps({'schema_version':2,'operations':[]})
    assert violations(v2_raw)==[('$','wire_version')]
    assert violations(json.dumps({'facts':[],'character_states':[],'open_threads':[],'timeline':[]}))==[('$','wire_version')]
    with pytest.raises(MemoryViolations) as e:
        parse_memory_result(v3(),PREV,'p2',PROSE,'evidence_delta',[],wire_version=2)
    assert e.value.violations==[Violation('$','wire_version')]


def test_v3_labels_are_humanized():
    with pytest.raises(MemoryViolations) as e:run(v3(facts_add=[padd('Ф',[])]))
    assert 'facts.add, елемент 1' in str(e.value)
