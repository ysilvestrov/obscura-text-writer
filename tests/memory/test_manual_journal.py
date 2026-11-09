import json
import pytest
from storygen.domain import StoryCreate,SceneCreate,RevisionConflict
from storygen.storage.repository import Repository
from storygen.memory.models import MemorySnapshot,MemoryEntry
from storygen.memory.journal import load_memory


def workspace(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Ручна пам’ять'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i))) for i in range(2)]
    ids=[]
    for i,scene in enumerate(scenes):
        ref=repo.save_version(story.id,scene.id,'manual',f'Доказ {i}.',[])
        repo.set_head(scene.id,'prose',ref.id,0);ids.append(ref.id)
    old=MemorySnapshot(facts=[MemoryEntry(text='Перший факт',source_version_id=ids[0],quote='Доказ 0.')],source_prose_ids=ids[:1])
    ref=repo.save_version(story.id,scenes[0].id,'memory',old.model_dump_json(),ids[:1])
    repo.set_head(scenes[0].id,'memory',ref.id,1)
    return repo,story,scenes,ids,old


def test_manual_v1_normalizes_to_v2_and_retains_previous_events(tmp_path):
    from storygen.memory.service import save_scene_memory
    repo,story,scenes,ids,old=workspace(tmp_path)
    data=old.model_copy(deep=True);data.source_prose_ids=ids
    data.timeline.append(MemoryEntry(text='Подія 2',source_version_id=ids[1],quote='Доказ 1.'))
    ref=save_scene_memory(repo,scenes[1].id,data.model_dump_json(),1)
    result=load_memory(repo.read_text(ref.id))
    assert result.events[:1]==load_memory(old.model_dump_json()).events
    assert result.schema_version==2 and ref.dependency_snapshot is not None
    assert repo.get_scene(scenes[1].id).heads['memory']==ref.id


def test_manual_cannot_rewrite_previous_prefix_even_with_valid_quote(tmp_path):
    from storygen.memory.service import save_scene_memory
    repo,story,scenes,ids,old=workspace(tmp_path)
    value=load_memory(old.model_dump_json()).model_dump();value['source_prose_ids']=ids
    value['events'][0]['text']='Інший висновок'
    with pytest.raises(ValueError,match='попередніх'):
        save_scene_memory(repo,scenes[1].id,json.dumps(value),1)
    assert 'memory' not in repo.get_scene(scenes[1].id).heads


def test_revision_checked_before_normalization_and_future_source_rejected(tmp_path):
    from storygen.memory.service import save_scene_memory
    repo,story,scenes,ids,old=workspace(tmp_path)
    with pytest.raises(RevisionConflict):save_scene_memory(repo,scenes[1].id,'bad JSON',0)
    future=MemorySnapshot(source_prose_ids=[ids[1]])
    with pytest.raises(ValueError):save_scene_memory(repo,scenes[0].id,future.model_dump_json(),2)


def test_fsck_checks_evidence_without_treating_reorder_as_corruption(tmp_path):
    from storygen.memory.service import save_scene_memory
    from storygen.storage.integrity import check_integrity
    repo,story,scenes,ids,old=workspace(tmp_path)
    value=old.model_copy(deep=True);value.source_prose_ids=ids
    save_scene_memory(repo,scenes[1].id,value.model_dump_json(),1)
    repo.reorder_scenes(story.id,[s.id for s in reversed(scenes)],repo.get_story(story.id).revision)
    assert check_integrity(tmp_path).ok
    bad=load_memory(old.model_dump_json()).model_dump();bad['events'][0]['quote']='Відсутній доказ'
    repo.save_version(story.id,scenes[0].id,'memory',json.dumps(bad),ids[:1])
    assert 'invalid_memory' in {issue.code for issue in check_integrity(tmp_path).issues}


def _manual_add(old,ids,supporting):
    from storygen.memory.journal import _add_event
    value=load_memory(old.model_dump_json());value=value.model_copy(update={'source_prose_ids':ids})
    event=_add_event('facts','Новий факт',ids[1],'Доказ 1.',0,supporting=supporting)
    return value.model_copy(update={'events':value.events+[event]})


def test_manual_save_keeps_supporting_quotes(tmp_path):
    from storygen.memory.service import save_scene_memory
    from storygen.memory.journal import _add_event
    repo,story,scenes,ids,old=workspace(tmp_path)
    data=_manual_add(old,ids,('Доказ',))
    ref=save_scene_memory(repo,scenes[1].id,data.model_dump_json(),1)
    new=load_memory(repo.read_text(ref.id)).events[-1]
    assert new.supporting_quotes==['Доказ']
    assert new.claim_id==_add_event('facts','Новий факт',ids[1],'Доказ 1.',0,supporting=('Доказ',)).claim_id


def test_manual_save_rejects_supporting_quote_outside_prose(tmp_path):
    from storygen.memory.service import save_scene_memory
    repo,story,scenes,ids,old=workspace(tmp_path)
    data=_manual_add(old,ids,('Чужа цитата',))
    with pytest.raises(ValueError,match='Новий запис потребує доказу поточної сцени'):
        save_scene_memory(repo,scenes[1].id,data.model_dump_json(),1)


def test_fsck_reports_bad_supporting_quote(tmp_path):
    from storygen.storage.integrity import check_integrity
    repo,story,scenes,ids,old=workspace(tmp_path)
    bad=json.loads(load_memory(old.model_dump_json()).model_dump_json())
    bad['events'][0]['supporting_quotes']=['Відсутній доказ']
    repo.save_version(story.id,scenes[0].id,'memory',json.dumps(bad),ids[:1])
    assert 'invalid_memory' in {issue.code for issue in check_integrity(tmp_path).issues}


MANUAL_PROSE='Перший рядок.\nДругий рядок.\nТретій рядок.'


def _manual_previous():
    from storygen.memory.journal import MemoryJournal,MemoryOperation,MemoryOperations,apply_operations
    return apply_operations(MemoryJournal(),MemoryOperations(operations=[
        MemoryOperation(action='add',category='open_threads',text='Лінія А',evidence_id='f000001'),
        MemoryOperation(action='add',category='open_threads',text='Лінія Б',evidence_id='f000001')]),'p1','Доказ.',[])


def test_manual_update_and_retire_keep_supporting_quotes_in_canonical_ids():
    from storygen.memory.journal import MemoryEvent,change_event_id,normalize_manual_memory
    previous=_manual_previous();first,second=(e.claim_id for e in previous.events)
    def change(action,claim,text,supporting):
        return MemoryEvent(event_id=f'hand-written-{action}',claim_id=claim,operation=action,category='open_threads',text=text,
            source_version_id='p2',quote='Перший рядок.',supporting_quotes=list(supporting))
    raw=previous.model_copy(update={'source_prose_ids':['p1','p2'],'events':previous.events+[
        change('update',first,'Лінія А змінилась',['Другий рядок.']),
        change('retire',second,'Лінія Б закрита',['Другий рядок.','Третій рядок.'])]}).model_dump_json()
    journal=normalize_manual_memory(raw,previous,'p2',MANUAL_PROSE,[])
    update,retire=journal.events[-2:]
    assert update.supporting_quotes==['Другий рядок.'] and retire.supporting_quotes==['Другий рядок.','Третій рядок.']
    assert update.event_id==change_event_id('update',first,'Лінія А змінилась','p2','Перший рядок.',['Другий рядок.'])
    assert retire.event_id==change_event_id('retire',second,'Лінія Б закрита','p2','Перший рядок.',['Другий рядок.','Третій рядок.'])
    assert update.event_id!=change_event_id('update',first,'Лінія А змінилась','p2','Перший рядок.')


def test_manual_duplicate_adds_differing_only_in_supporting_quotes_are_distinct_claims():
    from storygen.memory.journal import MemoryJournal,_add_event,normalize_manual_memory
    def add(supporting):
        return _add_event('facts','Той самий факт','p2','Перший рядок.',0,supporting=supporting)
    # An author may hand-write any unique IDs; normalization recomputes canonical ones.
    hand=[event.model_copy(update={'event_id':f'manual-{i}','claim_id':f'manual-claim-{i}'})
          for i,event in enumerate([add(()),add(('Другий рядок.',)),add(())])]
    raw=MemoryJournal(source_prose_ids=['p2'],events=hand).model_dump_json()
    journal=normalize_manual_memory(raw,MemoryJournal(),'p2',MANUAL_PROSE,[])
    plain,supported,repeat=journal.events
    # Different supporting quotes make a different key: both are occurrence 0; the exact repeat is occurrence 1.
    assert plain.claim_id==add(()).claim_id and supported.claim_id==add(('Другий рядок.',)).claim_id
    assert repeat.claim_id==_add_event('facts','Той самий факт','p2','Перший рядок.',1).claim_id
    assert len({plain.claim_id,supported.claim_id,repeat.claim_id})==3


def test_manual_resave_keeps_claim_ids_of_resolution_and_identical_fact():
    from storygen.memory.journal import MemoryJournal,_add_event,_change_event,normalize_manual_memory
    thread=_add_event('open_threads','Хто стукав','p1','Перший рядок.',0)
    previous=MemoryJournal(schema_version=3,source_prose_ids=['p1'],events=[thread])
    # Wire v4 order: the resolution fact first, then the model's identical facts.add, both occurrence 0 of their keys.
    new=[_change_event('retire',thread.claim_id,'Стукав сусід','open_threads',[],'p2','Другий рядок.'),
        _add_event('facts','Стукав сусід','p2','Другий рядок.',0,resolves_claim_id=thread.claim_id),
        _add_event('facts','Стукав сусід','p2','Другий рядок.',0)]
    raw=previous.model_copy(update={'source_prose_ids':['p1','p2'],'events':previous.events+new}).model_dump_json()
    journal=normalize_manual_memory(raw,previous,'p2',MANUAL_PROSE,[])
    assert [e.claim_id for e in journal.events[1:]]==[e.claim_id for e in new]


def _same_scene_closure(link):
    from storygen.memory.journal import MemoryEvent,MemoryJournal
    def event(id,claim,category,text,operation='add',resolves=None):
        return MemoryEvent(event_id=id,claim_id=claim,operation=operation,category=category,text=text,
            source_version_id='p2',quote='Перший рядок.',resolves_claim_id=resolves)
    return MemoryJournal(schema_version=3,source_prose_ids=['p2'],events=[
        event('e1','manual-thread','open_threads','Хто стукав'),
        event('e2','manual-thread','open_threads','Стукав сусід','retire'),
        event('e3','manual-fact','facts','Стукав сусід',resolves=link)]).model_dump_json()


def test_manual_normalization_remaps_resolution_links():
    from storygen.memory.journal import MemoryJournal,normalize_manual_memory
    from storygen.memory.projection import project_memory
    journal=normalize_manual_memory(_same_scene_closure('manual-thread'),MemoryJournal(),'p2',MANUAL_PROSE,[])
    text=project_memory(journal,[],{'p2':1}).text
    assert text.count('Стукав сусід')==1 and text.split('ХРОНОЛОГІЯ\n')[1]=='Немає.'
    thread,retire,fact=journal.events
    assert thread.claim_id!='manual-thread' and retire.claim_id==thread.claim_id and fact.resolves_claim_id==thread.claim_id


def test_manual_normalization_rejects_dangling_resolution_link():
    import pytest
    from storygen.memory.journal import MemoryJournal,normalize_manual_memory
    with pytest.raises(ValueError,match='невідомий запис'):
        normalize_manual_memory(_same_scene_closure('no-such-claim'),MemoryJournal(),'p2',MANUAL_PROSE,[])


def test_manual_slot_only_for_tracked_character():
    import pytest
    from storygen.memory.journal import MemoryJournal,_add_event,normalize_manual_memory
    def raw(cid):
        return MemoryJournal(schema_version=3,source_prose_ids=['p2'],
            events=[_add_event('character_states','Пальто','p2','Перший рядок.',0,[cid],slot='clothing')]).model_dump_json()
    with pytest.raises(ValueError,match='відстежуваного'):
        normalize_manual_memory(raw('B'),MemoryJournal(),'p2',MANUAL_PROSE,['A','B'],tracked=['A'])
    assert normalize_manual_memory(raw('A'),MemoryJournal(),'p2',MANUAL_PROSE,['A','B'],tracked=['A']).events[0].slot=='clothing'


def test_manual_save_rejects_slot_of_untracked_character(tmp_path):
    import pytest
    from storygen.domain import SceneCreate,StoryCreate
    from storygen.storage.repository import Repository
    from storygen.memory.journal import MemoryJournal,_add_event
    from storygen.memory.service import save_scene_memory
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Ядро'))
    scene=repo.create_scene(story.id,SceneCreate(title='1',beats='Вечір',character_ids=['A','B']))
    prose=repo.save_version(story.id,scene.id,'manual',MANUAL_PROSE,[])
    repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
    def raw(cid):
        return MemoryJournal(schema_version=3,source_prose_ids=[prose.id],
            events=[_add_event('character_states','Пальто',prose.id,'Перший рядок.',0,[cid],slot='clothing')]).model_dump_json()
    # Without cards the fallback protagonist is the first cast ID of the earliest scene: A.
    with pytest.raises(ValueError,match='відстежуваного'):
        save_scene_memory(repo,scene.id,raw('B'),repo.get_scene(scene.id).revision)
    save_scene_memory(repo,scene.id,raw('A'),repo.get_scene(scene.id).revision)
