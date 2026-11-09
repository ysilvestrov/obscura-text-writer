import json
from types import SimpleNamespace
import pytest
from storygen.memory import journal as J
from storygen.memory.journal import MemoryEvent,MemoryJournal,_add_event,_change_event,_extend,validate_memory_journal,normalize_manual_memory


def ev(**kw):
    base=dict(event_id='me_1',claim_id='mc_1',operation='add',category='facts',text='Текст',source_version_id='p1',quote='цитата')
    base.update(kw);return MemoryEvent(**base)


def state(text,slot='clothing',char='h',prose='p1',quote='цитата',occ=0):
    return _add_event('character_states',text,prose,quote,occ,[char],slot=slot)


def v3(sources,events):
    return MemoryJournal(schema_version=3,source_prose_ids=sources,events=events)


def test_default_fields_keep_v2_bytes_and_ids():
    e=_add_event('character_states','Ганна в халаті','p1','у халаті',0,['h'])
    assert (e.claim_id,e.event_id)==('mc_f8bdff65f39482d89d2863fb','me_e7cb35abc97edbe9929fd5f8')
    data=json.loads(e.model_dump_json())
    assert not {'slot','source_kind','evidence_version_id','resolves_claim_id'}&set(data)
    assert list(data)==['event_id','claim_id','operation','category','text','character_ids','source_version_id','quote']
    c=_change_event('update',e.claim_id,'Ганна в пальті','character_states',['h'],'p1','у пальті')
    assert c.event_id=='me_e04665188881b165567f1d84'
    assert J.change_event_id('update',e.claim_id,'Ганна в пальті','p1','у пальті')==c.event_id


def test_extra_fields_change_ids_and_serialize():
    plain=_add_event('character_states','Т','p1','ц',0,['h'])
    slotted=_add_event('character_states','Т','p1','ц',0,['h'],slot='clothing')
    assert slotted.claim_id!=plain.claim_id and slotted.event_id!=plain.event_id
    assert json.loads(slotted.model_dump_json())['slot']=='clothing'
    author=_add_event('facts','Т','p1','ц',0,source_kind='author',evidence_version_id='p0')
    data=json.loads(author.model_dump_json())
    assert data['source_kind']=='author' and data['evidence_version_id']=='p0'
    assert author.claim_id not in {plain.claim_id,slotted.claim_id}
    nq=_add_event('facts','Т','p1',None,0,source_kind='author')
    assert 'quote' not in json.loads(nq.model_dump_json())
    assert nq.claim_id!=_add_event('facts','Т','p1','ц',0,source_kind='author').claim_id
    r=_add_event('facts','Т','p1','ц',0,resolves_claim_id='mc_x')
    assert json.loads(r.model_dump_json())['resolves_claim_id']=='mc_x' and r.claim_id!=plain.claim_id
    a=J.change_event_id('update','mc_1','Т','p1','ц')
    assert J.change_event_id('update','mc_1','Т','p1','ц',slot='clothing')!=a
    ch=_change_event('update','mc_1','Т','character_states',['h'],'p1','ц',slot='clothing')
    assert ch.slot=='clothing' and ch.event_id==J.change_event_id('update','mc_1','Т','p1','ц',slot='clothing')


def test_author_without_quote_is_valid_only_for_author():
    ok=ev(source_kind='author',quote=None)
    assert ok.quote is None and 'quote' not in json.loads(ok.model_dump_json())
    with pytest.raises(ValueError):ev(quote=None)
    with pytest.raises(ValueError):ev(source_kind='author',quote=None,evidence_version_id='p0')
    with pytest.raises(ValueError):ev(source_kind='author',quote=None,supporting_quotes=['x'])
    with pytest.raises(ValueError):MemoryEvent(event_id='e',claim_id='c',operation='add',category='facts',text='т',source_version_id='p1')


def test_slot_requires_single_character_state_and_known_slot():
    assert ev(category='character_states',character_ids=['h'],slot='clothing').slot=='clothing'
    with pytest.raises(ValueError):ev(slot='clothing')
    with pytest.raises(ValueError):ev(category='character_states',character_ids=['a','b'],slot='clothing')
    with pytest.raises(ValueError):ev(category='character_states',slot='clothing')
    with pytest.raises(ValueError):ev(category='character_states',character_ids=['h'],slot='hat')


def test_replay_rejects_second_active_slot_value():
    a=state('Халат');b=state('Пальто',quote='цитата 2')
    with pytest.raises(ValueError):v3(['p1'],[a,b])
    other=state('Місто',slot='location');third=state('Інший',char='g')
    assert v3(['p1'],[a,other,third])
    retire=_change_event('retire',a.claim_id,'Халат','character_states',['h'],'p1','цитата',slot='clothing')
    assert v3(['p1'],[a,retire,b])


def test_update_cannot_change_slot():
    a=state('Халат')
    good=_change_event('update',a.claim_id,'Пальто','character_states',['h'],'p1','ц',slot='clothing')
    assert v3(['p1'],[a,good])
    for slot in ('body',None):
        bad=_change_event('update',a.claim_id,'Пальто','character_states',['h'],'p1','ц',slot=slot)
        with pytest.raises(ValueError):v3(['p1'],[a,bad])


def test_evidence_version_quote_checked_against_that_prose():
    sources={'pA':'Вона вдягла халат.','pB':'Потім вийшла надвір.'}
    def journal(quote='халат',**kw):
        return v3(['pA','pB'],[_add_event('facts','Факт','pB',quote,0,**kw)])
    assert validate_memory_journal(journal(source_kind='author',evidence_version_id='pA'),sources)
    with pytest.raises(ValueError):validate_memory_journal(journal('надвір',source_kind='author',evidence_version_id='pA'),sources)
    assert validate_memory_journal(journal(None,source_kind='author'),sources)
    with pytest.raises(ValueError):validate_memory_journal(journal(source_kind='author',evidence_version_id='pZ'),sources)
    late=_add_event('facts','Факт','pA','халат',0,source_kind='author',evidence_version_id='pB')
    with pytest.raises(ValueError):validate_memory_journal(v3(['pA','pB'],[late]),sources)


def test_extend_promotes_schema_version():
    prev=MemoryJournal(source_prose_ids=['p1'],events=[_add_event('facts','Т','p1','ц',0)])
    assert prev.schema_version==2
    assert _extend(prev,'p2',[_add_event('facts','Н','p2','ц',0)]).schema_version==2
    promoted=_extend(prev,'p2',[state('С',prose='p2')])
    assert promoted.schema_version==3
    assert _extend(prev,'p2',[_add_event('facts','Н','p2',None,0,source_kind='author')]).schema_version==3
    assert _extend(prev,'p2',[],3).schema_version==3
    assert _extend(promoted,'p3',[]).schema_version==3


def test_manual_memory_accepts_author_events():
    prev=MemoryJournal(source_prose_ids=['p1'],events=[_add_event('facts','Стара','p1','Перша сцена.',0)])
    prose='Друга сцена.';sources={'p1':'Перша сцена.','p2':prose}
    author=_add_event('facts','Таємниця','p2',None,0,source_kind='author')
    earlier=_add_event('facts','З минулого','p2','Перша сцена.',0,source_kind='author',evidence_version_id='p1')
    raw=v3(['p1','p2'],[*prev.events,author,earlier]).model_dump_json()
    result=normalize_manual_memory(raw,prev,'p2',prose,[])
    assert result.schema_version==3 and [e.source_version_id for e in result.events[1:]]==['p2','p2']
    assert result.events[1].quote is None and result.events[2].evidence_version_id=='p1'
    assert result.events[1].claim_id==author.claim_id and result.events[2].claim_id==earlier.claim_id
    validate_memory_journal(result,sources)
    bad=_add_event('facts','Хибна','p2','Нема такої.',0,source_kind='author',evidence_version_id='p1')
    result=normalize_manual_memory(v3(['p1','p2'],[*prev.events,bad]).model_dump_json(),prev,'p2',prose,[])
    with pytest.raises(ValueError):validate_memory_journal(result,sources)
    plain=_add_event('facts','Хибна','p2','Нема такої.',0)
    raw=MemoryJournal(source_prose_ids=['p1','p2'],events=[*prev.events,plain]).model_dump_json()
    with pytest.raises(ValueError):normalize_manual_memory(raw,prev,'p2',prose,[])


def test_tracked_characters_uses_protagonist():
    from storygen.memory.core import tracked_characters,slot_def,SLOTS,SLOT_REGISTRY_VERSION
    from storygen.characters.models import CharacterRecord
    entries=[dict(id='a0',text='Протагоніст',availability='timeless',available_from_scene_id=None,origin='author')]
    card=CharacterRecord.model_validate(dict(schema_version=2,id='A',name='Анна',entries=entries))
    scene=SimpleNamespace(id='1',position=0,character_ids=[],trashed_at=None)
    assert tracked_characters([card],[scene])==['A']
    assert tracked_characters([],[])==[]
    assert [s.name for s in SLOTS]==['clothing','carried','location','body','company']
    assert slot_def('location').expires_on_day_change is False and SLOT_REGISTRY_VERSION=='core-slots-v1'
    with pytest.raises(KeyError):slot_def('hat')
