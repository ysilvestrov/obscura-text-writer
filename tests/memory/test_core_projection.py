from types import SimpleNamespace
from storygen.memory.journal import MemoryEvent,MemoryJournal
from storygen.memory.projection import project_memory
from storygen.memory.forwarding import effective_hidden,memory_view_from_view

SUFFIX=' (читачеві невідомо: якщо знадобиться, введи в тексті як нове)'


def ev(id,category,text,*,op='add',claim=None,chars=(),slot=None,kind='prose',quote='доказ',resolves=None,source='p1',evidence=None):
    return MemoryEvent(event_id='e'+id,claim_id=claim or id,operation=op,category=category,text=text,character_ids=list(chars),
        source_version_id=source,quote=quote,slot=slot,source_kind=kind,resolves_claim_id=resolves,evidence_version_id=evidence)


def journal(*events):
    return MemoryJournal(schema_version=3,source_prose_ids=['p1'],events=list(events))


def core_journal():
    return journal(ev('loc','character_states','Квартира на Подолі',chars=['h'],slot='location'),
        ev('clo','character_states','Синій халат',chars=['h'],slot='clothing'),
        ev('mood','character_states','Ганна втомлена',chars=['h']),
        ev('f','facts','Ключ у сейфі'))


def test_core_section_first_and_not_filtered_by_cast():
    result=project_memory(core_journal(),['other'],{'p1':1},tracked=['h'],names={'h':'Ганна'})
    assert result.text.startswith('ЯДРО СТАНУ — Ганна\n')
    assert result.text.index('ЯДРО СТАНУ — Ганна')<result.text.index('ФАКТИ')
    assert 'одяг: Синій халат' in result.text
    # Unslotted states of an absent character are still filtered by the scene cast.
    assert 'Ганна втомлена' not in result.text
    assert result.metrics['projection_version']=='memory-uk-v3'


def test_core_lines_in_registry_order_skip_empty():
    text=project_memory(core_journal(),[],{'p1':1},tracked=['h'],names={'h':'Ганна'}).text
    core=text.split('\n\n')[0].splitlines()
    assert core==['ЯДРО СТАНУ — Ганна','одяг: Синій халат','місце: Квартира на Подолі']
    assert 'при собі' not in text and 'тілесний стан' not in text and 'з ким' not in text
    empty=project_memory(journal(ev('f','facts','Ключ у сейфі')),[],{'p1':1},tracked=['h'],names={'h':'Ганна'}).text
    assert 'ЯДРО СТАНУ' not in empty and empty.startswith('ФАКТИ')


def test_author_unquoted_value_has_reader_unknown_suffix():
    j=journal(ev('car','character_states','Пістолет у сумці',chars=['h'],slot='carried',kind='author',quote=None),
        ev('clo','character_states','Синій халат',chars=['h'],slot='clothing',kind='author'))
    text=project_memory(j,[],{'p1':1},tracked=['h'],names={'h':'Ганна'}).text
    assert 'при собі: Пістолет у сумці'+SUFFIX in text
    # An author record with a quote is known to the reader.
    assert 'одяг: Синій халат\n' in text+'\n' and 'одяг: Синій халат'+SUFFIX not in text


def test_slotted_states_not_duplicated_in_current_states():
    text=project_memory(core_journal(),[],{'p1':1},tracked=['h'],names={'h':'Ганна'}).text
    assert text.count('Синій халат')==1 and text.count('Квартира на Подолі')==1
    states=text.split('ПОТОЧНІ СТАНИ\n')[1].split('\n\n')[0]
    assert states=='— Ганна втомлена'
    # Without tracked characters (old callers) slotted states stay visible as ordinary states.
    legacy=project_memory(core_journal(),[],{'p1':1}).text
    assert 'ЯДРО СТАНУ' not in legacy and '— Синій халат' in legacy


def test_hidden_core_value_not_shown():
    result=project_memory(core_journal(),[],{'p1':1},hidden_claim_ids={'clo'},tracked=['h'],names={'h':'Ганна'})
    assert 'Синій халат' not in result.text and 'місце: Квартира на Подолі' in result.text
    assert result.metrics['hidden_claim_count']==1


def closed_journal():
    return journal(ev('t','open_threads','Хто вкрав ключ'),
        ev('r','open_threads','Ключ узяв сусід',op='retire',claim='t'),
        ev('fr','facts','Ключ узяв сусід',resolves='t'))


def test_v4_closure_rendered_only_as_fact():
    text=project_memory(closed_journal(),[],{'p1':1}).text
    facts=text.split('ФАКТИ\n')[1].split('\n\n')[0]
    timeline=text.split('ХРОНОЛОГІЯ\n')[1]
    assert facts=='— Ключ узяв сусід' and timeline=='Немає.'
    assert 'Хто вкрав ключ' not in text and text.count('Ключ узяв сусід')==1


def test_legacy_closure_stays_in_timeline():
    j=journal(ev('t','open_threads','Хто вкрав ключ'),ev('r','open_threads','Ключ узяв сусід',op='retire',claim='t'))
    text=project_memory(j,[],{'p1':1}).text
    assert text.split('ХРОНОЛОГІЯ\n')[1]=='— Сцена 1: Ключ узяв сусід'


def scene(**kw):
    base=dict(id='s1',story_id='st',position=0,title='Сцена 1',revision=0,memory_forwarding={},heads={'memory':'m1','prose':'p1'})
    base.update(kw);return SimpleNamespace(**base)


class View:
    def __init__(self,j,scenes,versions):
        self.j,self.scenes,self.versions=j,scenes,versions
    def get_scene(self,id):return next(s for s in self.scenes if s.id==id)
    peek_scene=get_scene
    def list_scenes(self,story_id):return list(self.scenes)
    peek_scenes=list_scenes
    def read_text(self,id):return self.j.model_dump_json()
    def get_version(self,id):return self.versions[id]


def version(scene_id,stale=False):
    return SimpleNamespace(scene_id=scene_id,story_id='st',stale=stale,dependency_snapshot=None)


def test_hidden_thread_resolution_stays_hidden():
    j=closed_journal()
    assert effective_hidden(j,{'t'})=={'t','fr'}
    assert effective_hidden(j,{'t'},forwarded={'fr'})=={'t'}
    assert effective_hidden(j,set())==set()
    text=project_memory(j,[],{'p1':1},hidden_claim_ids={'t'}).text
    assert 'Ключ узяв сусід' not in text and 'Хто вкрав ключ' not in text
    shown=project_memory(j,[],{'p1':1},hidden_claim_ids={'t'},forwarded_claim_ids={'fr'}).text
    assert shown.split('ФАКТИ\n')[1].split('\n\n')[0]=='— Ключ узяв сусід'
    def rows(first,second):
        scenes=[scene(memory_forwarding=first),scene(id='s2',position=1,title='Сцена 2',memory_forwarding=second,heads={'memory':'m2','prose':'p2'})]
        view=View(j,scenes,{'m2':version('s2'),'p1':version('s1')})
        return {row['claim_id']:row['forward'] for row in memory_view_from_view(view,'s2')['rows']}
    assert rows({},{})=={'t':True,'fr':True}
    assert rows({'t':False},{})=={'t':False,'fr':False}
    assert rows({},{'t':False})=={'t':False,'fr':False}
    # An explicit author choice for the resolution fact itself wins over the inherited mark.
    assert rows({'t':False},{'fr':True})=={'t':False,'fr':True}


def test_memory_view_title_follows_quote_version():
    j=MemoryJournal(schema_version=3,source_prose_ids=['p1','p2'],
        events=[ev('st','character_states','Ганна в пальті',chars=['h'],source='p2',evidence='p1')])
    scenes=[scene(),scene(id='s2',position=1,title='Сцена 2',heads={'memory':'m2','prose':'p2'})]
    view=View(j,scenes,{'m2':version('s2')})
    row=memory_view_from_view(view,'s2')['rows'][0]
    assert (row['source_title'],row['source_scene'],row['quote'])==('Сцена 1',1,'доказ')


def closed_thread_story(root):
    from storygen.domain import StoryCreate,SceneCreate
    from storygen.storage.repository import Repository
    from storygen.memory.journal import _add_event,_change_event
    repo=Repository(root);story=repo.create_story(StoryCreate(title='Лінії'))
    first=repo.create_scene(story.id,SceneCreate(title='1',beats='Пошук',character_ids=['A']))
    second=repo.create_scene(story.id,SceneCreate(title='2',beats='Далі',character_ids=['A']))
    prose=repo.save_version(story.id,first.id,'manual','Хтось украв ключ. Ключ узяв сусід.',[])
    repo.set_head(first.id,'prose',prose.id,repo.get_scene(first.id).revision)
    thread=_add_event('open_threads','Хто вкрав ключ',prose.id,'Хтось украв ключ',0)
    events=[thread,_change_event('retire',thread.claim_id,'Ключ узяв сусід','open_threads',[],prose.id,'Ключ узяв сусід'),
        _add_event('facts','Ключ узяв сусід',prose.id,'Ключ узяв сусід',0,resolves_claim_id=thread.claim_id)]
    j=MemoryJournal(schema_version=3,source_prose_ids=[prose.id],events=events)
    memory=repo.save_version(story.id,first.id,'memory',j.model_dump_json(),[prose.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    return repo,story,repo.get_scene(first.id),repo.get_scene(second.id),thread.claim_id,events[2].claim_id


def choose(repo,scene,choices):
    from storygen.memory.forwarding import memory_view,save_forwarding
    view=memory_view(repo,scene.id)
    return save_forwarding(repo,scene.id,choices,view['expected_revision'],view['fingerprint'])


def test_enabling_hidden_thread_resolution_stales_dependents(tmp_path):
    from storygen.generation.context import build_context
    from storygen.memory.forwarding import projection_policy
    from storygen.providers.models import RoleSettings,ProviderSettings
    repo,story,first,second,thread,fact=closed_thread_story(tmp_path)
    choose(repo,first,{thread:False})
    assert projection_policy(repo.context_view(story.id),second.id)==sorted({thread,fact})
    ctx=build_context(repo,second.id,'brief',RoleSettings(provider=ProviderSettings(model='test')))
    memory_block=lambda text:text.split('ЗДІЙСНЕНІ ПОДІЇ — ПЕРЕВІРЕНА ПАМ’ЯТЬ')[1].split('ЗАВЕРШЕННЯ ПОПЕРЕДНЬОЇ СЦЕНИ')[0]
    assert 'Ключ узяв сусід' not in memory_block(ctx.user_text)
    ref=repo.save_version(story.id,second.id,'brief','Завдання',ctx.input_refs,dependency_snapshot=ctx.dependency_snapshot)
    manual=repo.save_version(story.id,second.id,'brief','Ручне',[],manual_projection_policy=projection_policy(repo.context_view(story.id),second.id))
    assert not repo.get_version(ref.id).stale and not repo.get_version(manual.id).stale
    choose(repo,first,{fact:True})
    assert projection_policy(repo.context_view(story.id),second.id)==[thread]
    assert repo.get_version(ref.id).stale and repo.get_version(manual.id).stale
    assert 'Ключ узяв сусід' in memory_block(build_context(repo,second.id,'brief',RoleSettings(provider=ProviderSettings(model='test'))).user_text)


def test_policy_without_resolution_facts_equals_hidden_before(tmp_path):
    from tests.memory.test_forwarding import seeded,apply
    from storygen.memory.forwarding import projection_policy,hidden_before,memory_view
    repo,story,scenes=seeded(tmp_path)
    assert projection_policy(repo.context_view(story.id),scenes[2].id)==[]
    claim=memory_view(repo,scenes[1].id)['rows'][0]['claim_id']
    apply(repo,scenes[1],{claim:False})
    view=repo.context_view(story.id)
    assert projection_policy(view,scenes[2].id)==sorted(hidden_before(view,scenes[2].id))==[claim]


def test_core_header_without_card_name_uses_neutral_label():
    for names in (None,{},{'h':''}):
        text=project_memory(core_journal(),[],{'p1':1},tracked=['h'],names=names).text
        assert text.startswith('ЯДРО СТАНУ — протагоніст\n') and 'ЯДРО СТАНУ — h' not in text


def test_hidden_slot_stays_hidden_after_unknown():
    from tests.memory.test_wire_v4 import CLOTH,answer,core,dec,new,run
    j=run(answer(core(clothing=dec('unknown',reason='Новий день'))))
    retire,atmosphere=new(j)
    # The atmosphere state continues the retired slot claim and inherits its hidden mark (I5).
    assert atmosphere.resolves_claim_id==CLOTH.claim_id and retire.resolves_claim_id is None
    assert effective_hidden(j,{CLOTH.claim_id})=={CLOTH.claim_id,atmosphere.claim_id}
    hidden=project_memory(j,['h'],{'p1':1,'p2':2},hidden_claim_ids={CLOTH.claim_id},tracked=['h'],names={'h':'Ганна'}).text
    assert 'Халат' not in hidden
    # Without a hidden mark the link changes nothing: the value is an ordinary current state, not a closure.
    shown=project_memory(j,['h'],{'p1':1,'p2':2},tracked=['h'],names={'h':'Ганна'}).text
    assert '— Халат' in shown.split('ПОТОЧНІ СТАНИ\n')[1].split('\n\n')[0] and shown.split('ХРОНОЛОГІЯ\n')[1]=='Немає.'
    enabled=project_memory(j,['h'],{'p1':1,'p2':2},hidden_claim_ids={CLOTH.claim_id},forwarded_claim_ids={atmosphere.claim_id},
        tracked=['h'],names={'h':'Ганна'}).text
    assert '— Халат' in enabled
    def rows(first,second):
        scenes=[scene(memory_forwarding=first),scene(id='s2',position=1,title='Сцена 2',memory_forwarding=second,heads={'memory':'m2','prose':'p2'})]
        view=View(j,scenes,{'m2':version('s2'),'p1':version('s1'),'p2':version('s2')})
        return {row['claim_id']:row['forward'] for row in memory_view_from_view(view,'s2')['rows']}
    assert rows({CLOTH.claim_id:False},{})[atmosphere.claim_id] is False
    assert rows({CLOTH.claim_id:False},{atmosphere.claim_id:True})[atmosphere.claim_id] is True
    assert rows({},{})[atmosphere.claim_id] is True


def test_policy_includes_atmosphere_of_hidden_slot(tmp_path):
    from storygen.domain import StoryCreate,SceneCreate
    from storygen.storage.repository import Repository
    from storygen.memory.journal import _add_event,_change_event
    from storygen.memory.forwarding import projection_policy
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Слоти'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i),beats='Далі',character_ids=['A'])) for i in range(3)]
    text='Ганна в закривавленій сорочці.'
    def publish(scene,events,sources):
        prose=repo.save_version(story.id,scene.id,'manual',text,[],manual_projection_policy=projection_policy(repo.context_view(story.id),scene.id))
        repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
        built=events(prose.id);sources=sources+[prose.id]
        memory=repo.save_version(story.id,scene.id,'memory',MemoryJournal(schema_version=3,source_prose_ids=sources,events=built).model_dump_json(),sources)
        repo.set_head(scene.id,'memory',memory.id,repo.get_scene(scene.id).revision)
        return built,sources
    (cloth,),sources=publish(scenes[0],lambda p:[_add_event('character_states','Закривавлена сорочка',p,text,0,['A'],slot='clothing')],[])
    # The author hides the slot value at the first boundary; on the next day the model answers unknown.
    choose(repo,repo.get_scene(scenes[0].id),{cloth.claim_id:False})
    def unknown(p):
        return [cloth,_change_event('retire',cloth.claim_id,cloth.text,'character_states',['A'],p,text,slot='clothing',evidence_version_id=cloth.source_version_id),
            _add_event('character_states',cloth.text,p,text,0,['A'],evidence_version_id=cloth.source_version_id,resolves_claim_id=cloth.claim_id)]
    events,_=publish(scenes[1],unknown,sources)
    atmosphere=events[-1].claim_id
    assert projection_policy(repo.context_view(story.id),scenes[2].id)==sorted({cloth.claim_id,atmosphere})
    assert not next(r for r in memory_view_from_view(repo.context_view(story.id),scenes[1].id)['rows'] if r['claim_id']==atmosphere)['forward']
    choose(repo,repo.get_scene(scenes[1].id),{atmosphere:True})
    assert projection_policy(repo.context_view(story.id),scenes[2].id)==[cloth.claim_id]


def test_reader_unknown_marker_survives_unknown_decision():
    from tests.memory.test_wire_v4 import answer,core,dec,new,run
    j=run(answer(core(carried=dec('unknown',reason='Не згадано'))))
    atmosphere=new(j)[-1]
    assert (atmosphere.slot,atmosphere.source_kind,atmosphere.quote)==(None,'author',None)
    text=project_memory(j,['h'],{'p1':1,'p2':2},tracked=['h'],names={'h':'Ганна'}).text
    states=text.split('ПОТОЧНІ СТАНИ\n')[1].split('\n\n')[0].splitlines()
    assert '— Ключ'+SUFFIX in states
    # A quoted atmosphere state stays unmarked.
    assert '— Сутінки' in states
