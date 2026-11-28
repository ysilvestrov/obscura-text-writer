"""MEMORY-ENTITIES-S06: CAS storage of the entity overlay, author edits and model batches (no journal changes)."""
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import MemoryEntityMark, RevisionConflict
from storygen.memory.journal import MemoryJournal, _add_event, _change_event
from storygen.storage import locations as store
from storygen.storage import memory_entities as entities
from storygen.storage.context_view import ContextView
from storygen.web.app import create_app
from tests.generation.test_context_selection import story_with_memory
from tests.generation.test_memory_kind import claim

LIGHTHOUSE='Маяк стоїть на старій карті'
COAST='Подія на узбережжі номер 3: довгий опис того, що сталося біля води'
STATE='Синій халат'


def prepared(tmp_path):
    repo,scene,journal,prose=story_with_memory(tmp_path)
    story=repo.get_story(scene.story_id)
    cards=[{'schema_version':2,'id':i,'name':n,'entries':[]} for i,n in (('A','Анна'),('B','Борис'))]
    ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards),[])
    repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        (l1,)=store.ensure_locations(db,story.id,[('Маяк',)])
    return repo,scene,journal,prose,l1


def revision(repo,story_id):
    return repo.get_story(story_id).revision


def memory_head(repo,scene_id):
    ref=repo.get_scene(scene_id)
    return ref.heads['memory'],repo.get_version(ref.heads['memory']).sha256


@pytest.mark.req('MEMORY-ENTITIES')
def test_author_edit_is_stored_with_cas_and_without_journal_changes(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;cid=claim(journal,LIGHTHOUSE);rev=revision(repo,sid)
    head=memory_head(repo,repo.list_scenes(sid)[0].id)
    story=repo.update_memory_entities(sid,cid,['A'],[l1],rev)
    assert story.memory_entities[cid]==MemoryEntityMark(participant_ids=['A'],location_ids=[l1],source='author')
    assert story.revision==rev+1
    assert memory_head(repo,repo.list_scenes(sid)[0].id)==head
    again=repo.update_memory_entities(sid,cid,['A'],[l1],rev+1)
    assert again.revision==rev+1 and revision(repo,sid)==rev+1


@pytest.mark.req('MEMORY-ENTITIES')
def test_author_edit_replaces_both_fields(tmp_path):
    repo,scene,journal,prose,l1=prepared(tmp_path)
    sid=scene.story_id
    event=_add_event('facts','Факт з локацією',prose.id,'вдома',900,location_ids=[l1])
    first=repo.list_scenes(sid)[0]
    extended=MemoryJournal(schema_version=3,source_prose_ids=[prose.id],events=[*journal.events,event])
    memory=repo.save_version(sid,first.id,'memory',extended.model_dump_json(),[prose.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    story=repo.update_memory_entities(sid,event.claim_id,['A'],[],revision(repo,sid))
    assert story.memory_entities[event.claim_id]==MemoryEntityMark(participant_ids=['A'],location_ids=[],source='author')


@pytest.mark.req('MEMORY-ENTITIES')
def test_location_none_removes_the_mark(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;cid=claim(journal,LIGHTHOUSE)
    repo.update_memory_entities(sid,cid,['A'],[l1],revision(repo,sid))
    story=repo.update_memory_entities(sid,cid,['B'],None,revision(repo,sid))
    assert cid not in story.memory_entities
    rev=story.revision
    assert repo.update_memory_entities(sid,cid,[],None,rev).revision==rev
    repo.apply_entity_marks(sid,{cid:(['B'],[])},rev)
    story=repo.update_memory_entities(sid,cid,[],None,revision(repo,sid))
    assert story.memory_entities=={}


@pytest.mark.req('MEMORY-ENTITIES')
def test_stale_revision_is_a_conflict(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;cid=claim(journal,LIGHTHOUSE);stale=revision(repo,sid)-1
    with pytest.raises(RevisionConflict,match='розмітку сутностей не збережено'):
        repo.update_memory_entities(sid,cid,['A'],[l1],stale)
    with pytest.raises(RevisionConflict):
        repo.apply_entity_marks(sid,{cid:(['A'],[])},stale)
    with pytest.raises(RevisionConflict):
        repo.clear_entity_marks(sid,stale)
    assert repo.get_story(sid).memory_entities=={}


@pytest.mark.req('MEMORY-ENTITIES')
def test_unknown_claim_card_or_location_is_refused(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;cid=claim(journal,LIGHTHOUSE);rev=revision(repo,sid)
    with pytest.raises(ValueError,match='Запису немає в пам’яті твору'):
        repo.update_memory_entities(sid,'nope',['A'],[],rev)
    with pytest.raises(ValueError,match='Невідомий персонаж'):
        repo.update_memory_entities(sid,cid,['zz'],[],rev)
    with pytest.raises(ValueError,match='Невідома локація'):
        repo.update_memory_entities(sid,cid,['A'],['lz'],rev)
    assert revision(repo,sid)==rev


@pytest.mark.req('MEMORY-ENTITIES')
def test_author_participants_on_a_state_are_refused(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;cid=claim(journal,STATE)
    with pytest.raises(ValueError,match='Учасники дозволені лише для ліній, фактів і хронології'):
        repo.update_memory_entities(sid,cid,['A'],[],revision(repo,sid))
    story=repo.update_memory_entities(sid,cid,[],[l1],revision(repo,sid))
    assert story.memory_entities[cid].location_ids==[l1]


@pytest.mark.req('MEMORY-ENTITIES')
def test_model_batch_never_overwrites_the_author(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;f1=claim(journal,LIGHTHOUSE);f2=claim(journal,COAST)
    repo.update_memory_entities(sid,f1,['A'],[],revision(repo,sid))
    story,applied=repo.apply_entity_marks(sid,{f1:(['B'],[]),f2:(['A'],[])},revision(repo,sid))
    assert story.memory_entities[f1]==MemoryEntityMark(participant_ids=['A'],location_ids=[],source='author')
    assert story.memory_entities[f2]==MemoryEntityMark(participant_ids=['A'],location_ids=[],source='model')
    assert applied==[f2]


@pytest.mark.req('MEMORY-ENTITIES')
def test_model_batch_stores_no_participants_for_a_state(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;s1=claim(journal,STATE)
    story,applied=repo.apply_entity_marks(sid,{s1:(['A'],[l1])},revision(repo,sid))
    assert story.memory_entities[s1]==MemoryEntityMark(participant_ids=[],location_ids=[l1],source='model') and applied==[s1]


@pytest.mark.req('MEMORY-ENTITIES')
def test_model_batch_with_an_unknown_claim_is_refused_whole(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;rev=revision(repo,sid)
    with pytest.raises(ValueError,match='Запису немає в пам’яті твору'):
        repo.apply_entity_marks(sid,{claim(journal,COAST):(['A'],[]),'nope':(['A'],[])},rev)
    with pytest.raises(ValueError,match='Невідомий персонаж'):
        repo.apply_entity_marks(sid,{claim(journal,COAST):(['zz'],[])},rev)
    story=repo.get_story(sid)
    assert story.memory_entities=={} and story.revision==rev


@pytest.mark.req('MEMORY-ENTITIES')
def test_clear_removes_only_model_marks(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;f1=claim(journal,LIGHTHOUSE);f2=claim(journal,COAST)
    repo.update_memory_entities(sid,f1,['A'],[],revision(repo,sid))
    repo.apply_entity_marks(sid,{f2:(['B'],[])},revision(repo,sid))
    story=repo.clear_entity_marks(sid,revision(repo,sid))
    assert set(story.memory_entities)=={f1}
    rev=story.revision
    assert repo.clear_entity_marks(sid,rev).revision==rev
    with pytest.raises(ValueError):
        repo.clear_entity_marks(sid,rev,'author')


@pytest.mark.req('MEMORY-ENTITIES')
def test_too_many_marks_are_refused(tmp_path,monkeypatch):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;f1=claim(journal,LIGHTHOUSE);f2=claim(journal,COAST)
    monkeypatch.setattr(entities,'MAX_ENTITY_MARKS',1)
    repo.update_memory_entities(sid,f1,['A'],[],revision(repo,sid))
    with pytest.raises(ValueError,match='Забагато записів розмітки сутностей'):
        repo.update_memory_entities(sid,f2,['A'],[],revision(repo,sid))
    with pytest.raises(ValueError,match='Забагато записів розмітки сутностей'):
        repo.apply_entity_marks(sid,{f2:(['A'],[])},revision(repo,sid))
    assert repo.update_memory_entities(sid,f1,['B'],[],revision(repo,sid)).memory_entities[f1].participant_ids==['B']


@pytest.mark.req('MEMORY-ENTITIES')
def test_book_claims_take_timeline_and_records_of_every_head(tmp_path):
    repo,scene,journal,prose,l1=prepared(tmp_path)
    sid=scene.story_id;first=repo.list_scenes(sid)[0]
    retire=_change_event('retire',claim(journal,STATE),STATE,'character_states',['A'],prose.id,'в халаті',slot='clothing')
    extra=_add_event('facts','Факт другої сцени',prose.id,'вдома',901)
    closed=MemoryJournal(schema_version=3,source_prose_ids=[prose.id],events=[*journal.events,retire])
    memory=repo.save_version(sid,first.id,'memory',closed.model_dump_json(),[prose.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    second_journal=MemoryJournal(schema_version=3,source_prose_ids=[prose.id],events=[extra])
    memory=repo.save_version(sid,scene.id,'memory',second_journal.model_dump_json(),[prose.id])
    repo.set_head(scene.id,'memory',memory.id,repo.get_scene(scene.id).revision)
    with repo.db.connection() as db:
        view=ContextView(repo,db,sid)
        found=entities.book_claims(view,sid)
    assert extra.claim_id in found and claim(journal,LIGHTHOUSE) in found
    assert claim(journal,'Сталася подія 0') in found
    assert claim(journal,STATE) not in found


@pytest.mark.req('MEMORY-ENTITIES')
def test_entity_resolver_uses_cards_and_merges(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id
    repo.update_memory_entities(sid,claim(journal,LIGHTHOUSE),['A'],[l1],revision(repo,sid))
    with repo.db.connection() as db:
        view=ContextView(repo,db,sid)
        resolver=entities.entity_resolver(view,view.story)
    assert resolver.known_cards=={'A','B'} and set(resolver.marks)=={claim(journal,LIGHTHOUSE)}


@pytest.mark.req('MEMORY-ENTITIES')
def test_memory_entities_http(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    sid=scene.story_id;cid=claim(journal,LIGHTHOUSE);rev=revision(repo,sid)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        url=f'/api/stories/{sid}/memory-entities'
        body={'claim_id':cid,'participant_ids':['A'],'location_ids':[l1],'expected_revision':rev}
        response=client.put(url,json=body)
        assert response.status_code==200 and response.json()['revision']==rev+1
        assert response.json()['memory_entities'][cid]['source']=='author'
        assert client.put(url,json=body).status_code==409
        assert client.put(url,json={**body,'claim_id':'nope','expected_revision':rev+1}).status_code==400
        assert client.put(url,json={**body,'participant_ids':['A']*201,'expected_revision':rev+1}).status_code==422
        cleared=client.post(url+'/clear',json={'expected_revision':rev+1})
        assert cleared.status_code==200 and cleared.json()['revision']==rev+1
        assert client.post(url+'/clear',json={'expected_revision':rev}).status_code==409
