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
