"""MEMORY-ENTITIES-S07 in the request: the overlay enters selection and the narrowed catalog only (Р3); the rest stays byte-identical (І1, І6)."""
import json
import pathlib

import pytest

from storygen.generation.context import SELECTED_PROJECTION, build_context
from storygen.storage import memory_entities as entities
from tests.generation.cardless_memory import cardless_memory_request
from tests.generation.test_context_selection import memory_section, settings
from tests.generation.test_memory_kind import claim
from tests.storage.test_memory_entities_store import prepared

GOLDEN=pathlib.Path(__file__).parent/'golden'/'memory_request_no_cards.json'
COAST='Подія на узбережжі номер 3: довгий опис того, що сталося біля води'


def mark(repo,story_id,marks):
    return entities.apply_entity_marks(repo,story_id,marks,repo.get_story(story_id).revision)


def tight(repo,scene):
    full=build_context(repo,scene.id,'brief',settings())
    return settings(max_input_chars=len(full.system_text)+len(full.user_text)-400)


@pytest.mark.req('MEMORY-ENTITIES')
def test_fitting_request_with_marks_is_byte_identical(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    before=build_context(repo,scene.id,'brief',settings())
    story,applied=mark(repo,scene.story_id,{claim(journal,COAST):(['B'],[l1])})
    assert applied
    after=build_context(repo,scene.id,'brief',settings())
    assert (after.user_text,after.fingerprint)==(before.user_text,before.fingerprint)
    assert after.memory_metrics==before.memory_metrics


@pytest.mark.req('MEMORY-ENTITIES')
def test_overflowing_request_selects_by_the_overlay(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    limit=tight(repo,scene)
    plain=build_context(repo,scene.id,'brief',limit)
    assert COAST not in memory_section(plain)
    mark(repo,scene.story_id,{claim(journal,COAST):(['B'],[])})
    marked=build_context(repo,scene.id,'brief',limit)
    assert COAST in memory_section(marked) and marked.memory_metrics['projection_version']==SELECTED_PROJECTION


@pytest.mark.req('MEMORY-ENTITIES')
def test_overlay_location_does_not_return_an_absent_state_to_the_projection(tmp_path):
    repo,scene,journal,_,l1=prepared(tmp_path)
    repo.update_scene_metadata(scene.id,{'character_ids':['A']},repo.get_scene(scene.id).revision)
    state='Борис тримає річ номер 3'
    before=build_context(repo,scene.id,'brief',settings())
    assert state not in memory_section(before) and before.memory_metrics['omitted_state_count']==10
    mark(repo,scene.story_id,{claim(journal,state):([],[l1])})
    after=build_context(repo,scene.id,'brief',settings())
    assert state not in memory_section(after)
    assert after.memory_metrics['omitted_state_count']==10 and after.user_text==before.user_text


def narrow_story(tmp_path):
    from storygen.domain import SceneCreate, StoryCreate
    from storygen.memory.journal import MemoryJournal, _add_event
    from storygen.storage.repository import Repository
    from tests.link_helpers import approve_links
    repo=Repository(tmp_path);item=repo.create_story(StoryCreate(title='Каталог'))
    cards=[{'schema_version':2,'id':i,'name':n,'entries':[]} for i,n in (('A','Анна'),('B','Борис'))]
    ref=repo.save_version(item.id,None,'character_cards',json.dumps(cards),[])
    repo.publish_story_material(item.id,'characters_version_id',ref.id,repo.get_story(item.id).revision)
    first,second=(repo.create_scene(item.id,SceneCreate(title=t,beats='Вдома',character_ids=cast)) for t,cast in (('1',['A','B']),('2',['A'])))
    p1=repo.save_version(item.id,first.id,'manual','Анна і Борис удома.',[])
    repo.set_head(first.id,'prose',p1.id,repo.get_scene(first.id).revision)
    events=[_add_event('character_states','Анна втомлена',p1.id,'удома',0,['A']),_add_event('facts','Скеля стоїть біля бухти',p1.id,'удома',1)]
    events+=[_add_event('character_states',f'Борис тримає річ номер {n} у старій шафі на горищі',p1.id,'удома',10+n,['B']) for n in range(40)]
    journal=MemoryJournal(schema_version=4,source_prose_ids=[p1.id],events=events)
    memory=repo.save_version(item.id,first.id,'memory',journal.model_dump_json(),[p1.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    p2=repo.save_version(item.id,second.id,'manual','Анна дивиться на дощ.',[])
    repo.set_head(second.id,'prose',p2.id,repo.get_scene(second.id).revision)
    approve_links(repo,item.id)
    return repo,repo.get_scene(second.id),journal


@pytest.mark.req('MEMORY-ENTITIES')
def test_narrowed_memory_stage_uses_the_overlay(tmp_path):
    from tests.generation.test_memory_stage_narrow import chars,role
    repo,scene,journal=narrow_story(tmp_path)
    fact=claim(journal,'Скеля стоїть біля бухти')
    full=build_context(repo,scene.id,'memory',role())
    tight=role(max_input_chars=chars(full)-500)
    plain=build_context(repo,scene.id,'memory',tight)
    assert plain.memory_metrics['projection_version']=='memory-catalog-v4-narrow'
    assert 'Скеля стоїть біля бухти' not in plain.user_text
    mark(repo,scene.story_id,{fact:(['A'],[])})
    marked=build_context(repo,scene.id,'memory',tight)
    assert 'Скеля стоїть біля бухти' in marked.user_text
    assert marked.memory_metrics['narrow']['immutable_shown']==plain.memory_metrics['narrow']['immutable_shown']+1


@pytest.mark.req('MEMORY-ENTITIES')
def test_memory_request_without_cards_matches_the_golden(tmp_path):
    from tests.generation.cardless_memory import cardless_memory_request
    assert cardless_memory_request(tmp_path)==json.loads(GOLDEN.read_text(encoding='utf-8'))
