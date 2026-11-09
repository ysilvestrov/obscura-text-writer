import json
from storygen.memory.core import SLOTS
from storygen.memory.journal import (MemoryJournal, MemoryOperation, MemoryOperations, _add_event, apply_operations,
    replay_memory, validate_memory_journal)
from storygen.memory.wire_v4 import MemoryWireV4, check_v4, schema_bounds_v4, wire_v4_events
from tests.memory.wire_helpers import v3_response, v4_response

PROSE_1='Ганна в халаті.\nПерша сцена.'
PROSE='Ганна вдягла пальто.\nУ кишені ключ.\nСтукав сусід.\nНадворі ніч.\nЛист на столі.'
LINE=dict(enumerate(PROSE.split('\n'),1))
CLOTH=_add_event('character_states','Халат','p1','Ганна в халаті.',0,['h'],slot='clothing')
CARRIED=_add_event('character_states','Ключ','p1',None,0,['h'],slot='carried',source_kind='author')
MOOD=_add_event('character_states','Сутінки','p1','Перша сцена.',0,['h'])
T1=_add_event('open_threads','Хто стукав?','p1','Перша сцена.',0)
T2=_add_event('open_threads','Де лист?','p1','Ганна в халаті.',0)
PREV=MemoryJournal(schema_version=3,source_prose_ids=['p1'],events=[CLOTH,CARRIED,MOOD,T1,T2])
BOUNDS=schema_bounds_v4(PREV,PROSE,['h'],['h'],{'h':False})
SOURCES={'p1':PROSE_1,'p2':PROSE}


def dec(status='unchanged',text='',ev=(),reason=''):return {'status':status,'text':text,'evidence_ids':list(ev),'reason':reason}
def tdec(status='open',resolution='',ev=()):return {'status':status,'resolution':resolution,'evidence_ids':list(ev)}
def padd(text,ids):return {'text':text,'evidence_ids':ids}
def sadd(text,ids,chars=()):return {'text':text,'evidence_ids':ids,'character_ids':list(chars)}
def chg(claim,text,ids):return {'claim_id':claim,'text':text,'evidence_ids':ids}
def three(prefix):return [padd(f'{prefix}{i}',['f000001']) for i in range(3)]


def core(**slots):
    base={s.name:dec() for s in SLOTS};base.update(slots)
    return {'h':base}


def threads(**over):
    base={T1.claim_id:tdec(),T2.claim_id:tdec()};base.update(over)
    return base


def answer(core_=None,threads_=None,**groups):
    return json.loads(v4_response(core() if core_ is None else core_,threads() if threads_ is None else threads_,**groups))


def run(data,prev=PREV,bounds=BOUNDS,sources=SOURCES):
    assert check_v4(data,prev,bounds)==[]
    journal=wire_v4_events(MemoryWireV4.model_validate(data),prev,'p2',PROSE,bounds)
    validate_memory_journal(journal,sources)
    return journal


def bad(data,prev=PREV,bounds=BOUNDS):
    return [tuple(v) for v in check_v4(data,prev,bounds)]


def new(journal,prev=PREV):return journal.events[len(prev.events):]


def test_bounds_shape():
    assert BOUNDS['tracked']=={'h':[s.name for s in SLOTS]} and BOUNDS['unestablished']=={'h':['carried']}
    assert BOUNDS['threads']==[T1.claim_id,T2.claim_id] and BOUNDS['mutable']=={'character_states':[MOOD.claim_id]}
    assert BOUNDS['fragment_ids']==[f'f00000{i}' for i in range(1,6)] and BOUNDS['character_ids']==['h']
    assert BOUNDS['day_change']=={'h':False} and BOUNDS['slot_registry']=='core-slots-v1'
    assert schema_bounds_v4(PREV,PROSE,[],['h'],{})['tracked']=={}


def test_changed_into_empty_slot_adds_slotted_state():
    (event,)=new(run(answer(core(location=dec('changed','Двір',['f000004'])))))
    assert (event.operation,event.slot,event.character_ids,event.text)==('add','location',['h'],'Двір')
    assert (event.source_version_id,event.quote,event.source_kind)==('p2',LINE[4],'prose')


def test_changed_into_occupied_slot_updates_same_claim():
    j=run(answer(core(clothing=dec('changed','Пальто',['f000001','f000002']))))
    (event,)=new(j)
    assert (event.operation,event.claim_id,event.slot,event.text)==('update',CLOTH.claim_id,'clothing','Пальто')
    assert event.quote==LINE[1] and event.supporting_quotes==[LINE[2]]
    assert replay_memory(j)[CLOTH.claim_id].text=='Пальто'


def test_unknown_moves_value_to_atmosphere():
    j=run(answer(core(clothing=dec('unknown',reason='Новий день'))))
    retire,add=new(j)
    assert (retire.operation,retire.claim_id,retire.slot,retire.text)==('retire',CLOTH.claim_id,'clothing','Халат')
    assert (add.operation,add.slot,add.text,add.character_ids,add.category)==('add',None,'Халат',['h'],'character_states')
    for event in (retire,add):
        assert (event.source_version_id,event.quote,event.evidence_version_id,event.source_kind)==('p2','Ганна в халаті.','p1','prose')
    active=replay_memory(j)
    assert CLOTH.claim_id not in active and add.claim_id in active


def test_unknown_of_author_unquoted_slot():
    j=run(answer(core(carried=dec('unknown',reason='Не згадано'))))
    retire,add=new(j)
    assert (retire.operation,retire.claim_id,retire.slot)==('retire',CARRIED.claim_id,'carried')
    for event in (retire,add):
        assert (event.source_kind,event.quote,event.evidence_version_id,event.source_version_id)==('author',None,None,'p2')
    assert add.slot is None and add.text=='Ключ'


def test_unknown_of_empty_slot_has_no_events():
    assert new(run(answer(core(body=dec('unknown',reason='Не видно')))))==[]


def test_introduced_converts_author_value_to_prose():
    j=run(answer(core(carried=dec('introduced',ev=['f000002']))))
    (event,)=new(j)
    assert (event.operation,event.claim_id,event.slot,event.text)==('update',CARRIED.claim_id,'carried','Ключ')
    assert (event.source_kind,event.quote,event.evidence_version_id)==('prose',LINE[2],None)


def test_introduced_only_for_unestablished_slot():
    assert bad(answer(core(clothing=dec('introduced',ev=['f000001']))))==[('core.h.clothing','target_unknown')]
    assert bad(answer(core(location=dec('introduced',ev=['f000001']))))==[('core.h.location','target_unknown')]


def test_closed_thread_retires_and_adds_resolution_fact():
    j=run(answer(threads_=threads(**{T1.claim_id:tdec('closed','Стукав сусід',['f000003','f000004'])})))
    retire,fact=new(j)
    assert (retire.operation,retire.claim_id,retire.text,retire.category)==('retire',T1.claim_id,'Стукав сусід','open_threads')
    assert (fact.operation,fact.category,fact.text,fact.resolves_claim_id)==('add','facts','Стукав сусід',T1.claim_id)
    for event in (retire,fact):
        assert (event.quote,event.supporting_quotes,event.source_version_id)==(LINE[3],[LINE[4]],'p2')
    assert T1.claim_id not in replay_memory(j)


def test_missing_slot_or_thread_key_is_schema_violation():
    partial=core();del partial['h']['clothing']
    assert bad(answer(partial))==[('core.h.clothing','schema')]
    assert bad(answer({}))==[('core.h','schema')]
    one=threads();del one[T2.claim_id]
    assert bad(answer(threads_=one))==[(f'threads.{T2.claim_id}','schema')]
    extra=core();extra['h']['hat']=dec()
    assert bad(answer(extra))==[('core.h','schema')]
    assert bad(answer(threads_=threads(mc_zzz=tdec())))==[('threads','schema')]


def test_unused_fields_are_ignored_not_rejected():
    # Models fill every key of a strict schema, e.g. a reason for a change; the server ignores fields the status does not use.
    assert bad(answer(core(body=dec(text='x',reason='без змін'))))==[]
    assert bad(answer(core(body=dec(ev=['f000001']))))==[]
    assert bad(answer(core(clothing=dec('changed','Пальто',['f000001'],reason='Зняла халат'))))==[]
    assert bad(answer(core(clothing=dec('unknown','Халат',['f000009'],reason='Не видно'))))==[]
    assert bad(answer(threads_=threads(**{T1.claim_id:tdec(resolution='ще ні',ev=['f000001'])})))==[]
    (event,)=new(run(answer(core(carried=dec('introduced','Інше',['f000002'],reason='x')))))
    assert (event.text,event.quote)==('Ключ',LINE[2])
    assert new(run(answer(core(body=dec(text='x',reason='без змін')))))==[]


def test_required_fields_and_status_are_still_checked():
    assert bad(answer(core(clothing=dec('unknown'))))==[('core.h.clothing','schema')]
    assert bad(answer(core(clothing=dec('changed',' ',['f000001']))))==[('core.h.clothing','schema')]
    assert bad(answer(core(clothing=dec('mystery'))))==[('core.h.clothing','schema')]
    assert bad(answer(threads_=threads(**{T1.claim_id:tdec('closed','',['f000001'])})))==[(f'threads.{T1.claim_id}','schema')]
    assert bad(answer(core(clothing=dec('changed','П',[]))))==[('core.h.clothing','evidence_count')]
    assert bad(answer(core(clothing=dec('changed','П',['f000009']))))==[('core.h.clothing','evidence_unknown')]
    assert bad(answer(threads_=threads(**{T1.claim_id:tdec('closed','Р',['f000001','f000001'])})))==[(f'threads.{T1.claim_id}','evidence_count')]
    assert bad(answer(threads_=threads(**{T1.claim_id:tdec('closed','Р',['f000099'])})))==[(f'threads.{T1.claim_id}','evidence_unknown')]


def test_thirteen_closed_threads_are_valid():
    lines=[_add_event('open_threads',f'Лінія {i}','p1','Перша сцена.',0) for i in range(13)]
    prev=MemoryJournal(schema_version=3,source_prose_ids=['p1'],events=lines)
    bounds=schema_bounds_v4(prev,PROSE,['h'],['h'],{'h':False})
    data=answer(threads_={e.claim_id:tdec('closed',f'Розв’язка {i}',['f000003']) for i,e in enumerate(lines)})
    assert check_v4(data,prev,bounds)==[]
    j=run(data,prev,bounds)
    assert len(new(j,prev))==26 and not any(e.category=='open_threads' for e in replay_memory(j).values())


def test_add_limits_still_apply():
    four=[padd(f'Ф{i}',['f000001']) for i in range(4)]
    assert bad(answer(facts_add=four))==[('facts.add','add_limit')]
    states=[sadd(f's{i}',['f000001']) for i in range(3)]
    found=bad(answer(facts_add=four,timeline_add=three('t'),open_threads_add=three('o'),character_states_add=states))
    assert ('$','ops_limit') in found and ('facts.add','add_limit') in found
    full=answer(facts_add=three('f'),timeline_add=three('t'),open_threads_add=three('o'),character_states_add=states,
        character_states_update=[chg(MOOD.claim_id,'Ніч',['f000004'])])
    assert bad(full)==[]


def test_state_changes_only_for_unslotted_claims():
    assert bad(answer(character_states_update=[chg(CLOTH.claim_id,'П',['f000001'])]))==[('character_states.update[0]','target_unknown')]
    assert bad(answer(character_states_retire=[chg(CARRIED.claim_id,'К',['f000002'])]))==[('character_states.retire[0]','target_unknown')]
    (event,)=new(run(answer(character_states_retire=[chg(MOOD.claim_id,'Ніч',['f000004'])])))
    assert (event.operation,event.claim_id,event.slot)==('retire',MOOD.claim_id,None)
    data=answer();data['open_threads']['update']=[]
    assert bad(data)==[('open_threads.update','schema')]


def test_core_absent_character_has_no_keys():
    bounds=schema_bounds_v4(PREV,PROSE,[],['h'],{'h':False})
    assert new(run(answer({}),bounds=bounds))==[]
    assert bad(answer(),bounds=bounds)==[('core','schema')]


def test_v4_on_v2_previous_without_core():
    prev=apply_operations(MemoryJournal(),MemoryOperations(operations=[
        MemoryOperation(action='add',category='facts',text='Факт',evidence_id='f000001'),
        MemoryOperation(action='add',category='open_threads',text='Лінія',evidence_id='f000002')]),'p1',PROSE_1,[])
    assert prev.schema_version==2
    bounds=schema_bounds_v4(prev,PROSE,['h'],['h'],{'h':True})
    line=prev.events[1].claim_id
    j=run(answer(threads_={line:tdec()}),prev,bounds)
    assert j.schema_version==3 and new(j,prev)==[] and j.source_prose_ids==['p1','p2']


def test_v3_answer_gets_wire_version():
    assert bad(json.loads(v3_response()))==[('$','wire_version')]
    assert bad({**answer(),'schema_version':5})==[('$','schema')]
    assert bad([])==[('$','schema')]


def test_translation_order_is_deterministic():
    data=answer(core(clothing=dec('changed','Пальто',['f000001']),carried=dec('introduced',ev=['f000002']),
            location=dec('changed','Двір',['f000004'])),
        threads(**{T1.claim_id:tdec('closed','Сусід',['f000003'])}),
        facts_add=[padd('Ф',['f000005'])],character_states_add=[sadd('С',['f000004'],['h'])],
        character_states_update=[chg(MOOD.claim_id,'Ніч',['f000004'])],open_threads_add=[padd('Л',['f000005'])],
        timeline_add=[padd('Т',['f000003'])])
    order=[(e.operation,e.category,e.slot,e.text) for e in new(run(data))]
    assert order==[('update','character_states','clothing','Пальто'),('update','character_states','carried','Ключ'),
        ('add','character_states','location','Двір'),('retire','open_threads',None,'Сусід'),('add','facts',None,'Сусід'),
        ('add','facts',None,'Ф'),('add','character_states',None,'С'),('update','character_states',None,'Ніч'),
        ('add','open_threads',None,'Л'),('add','timeline',None,'Т')]
    assert run(data)==run(json.loads(json.dumps(data)))


ANNA_KEY=_add_event('character_states','Ключ Ганни','p1','Ганна в халаті.',0,['a'],slot='carried')


def test_former_protagonist_slot_is_mutable_state(tmp_path):
    # Anna ('a') lost the protagonist mark to Bohdan ('h'): her slot claims are ordinary mutable states, never core.
    from storygen.memory.projection import memory_catalog_v4
    prev=MemoryJournal(schema_version=3,source_prose_ids=['p1'],events=[CLOTH,CARRIED,MOOD,ANNA_KEY,T1,T2])
    bounds=schema_bounds_v4(prev,PROSE,['h','a'],['h'],{'h':False})
    assert bounds['tracked']=={'h':[s.name for s in SLOTS]}
    assert bounds['mutable']=={'character_states':[MOOD.claim_id,ANNA_KEY.claim_id]}
    catalog=json.loads(memory_catalog_v4(prev,['h'],{'h':'Ганна'}))
    assert set(catalog['core'])=={'h'}
    assert [m['claim_id'] for m in catalog['mutable']]==[MOOD.claim_id,ANNA_KEY.claim_id]
    (event,)=new(run(answer(character_states_retire=[chg(ANNA_KEY.claim_id,'Ключ віддано',['f000002'])]),prev,bounds),prev)
    assert (event.operation,event.claim_id,event.slot)==('retire',ANNA_KEY.claim_id,'carried')
    (event,)=new(run(answer(character_states_update=[chg(ANNA_KEY.claim_id,'Ключ у сумці',['f000002'])]),prev,bounds),prev)
    assert (event.operation,event.claim_id,event.text)==('update',ANNA_KEY.claim_id,'Ключ у сумці')
    # Old captured bounds (slot claims never mutable) keep rejecting the same change.
    old={**bounds,'mutable':{'character_states':[MOOD.claim_id]}}
    assert bad(answer(character_states_retire=[chg(ANNA_KEY.claim_id,'К',['f000002'])]),prev,old)==[('character_states.retire[0]','target_unknown')]
    # The memory context passes every tracked character, so the catalog and bounds agree with the cast.
    from storygen.generation.context import build_context
    from tests.memory.test_core_review import role, two_scenes
    from tests.storage.test_memory_core_selectors import cards
    repo,story,_,s2,_,claims=two_scenes(tmp_path)
    repo.publish_story_material(story.id,'characters_version_id',cards(repo,story.id,'B'),repo.get_story(story.id).revision)
    context=build_context(repo,s2.id,'memory',role())
    live=json.loads(context.fragments['memory_schema_bounds'])
    assert live['tracked']=={} and live['mutable']['character_states']==[claims['cloth'].claim_id,claims['key'].claim_id]
    assert claims['cloth'].claim_id in context.user_text


def test_tracked_slot_still_only_via_core():
    # I1 for the tracked character holds whether or not the character is in the scene's cast.
    for bounds in (BOUNDS,schema_bounds_v4(PREV,PROSE,[],['h'],{'h':False})):
        data=answer(character_states_update=[chg(CLOTH.claim_id,'П',['f000001'])])
        if not bounds['tracked']:data['core']={}
        assert bad(data,bounds=bounds)==[('character_states.update[0]','target_unknown')]
    assert MOOD.claim_id in BOUNDS['mutable']['character_states'] and CLOTH.claim_id not in BOUNDS['mutable']['character_states']
