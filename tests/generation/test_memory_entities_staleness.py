"""MEMORY-ENTITIES-S07: the selector scene/memory_entities stales only versions built with selection or a narrowed catalog,
and only when the effective entities of the candidates before the scene changed (Р8)."""
import pytest

from storygen.dependency_models import DependencySnapshot
from storygen.generation.context import build_context
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.storage import memory_entities as entities
from storygen.storage.snapshots import compare_snapshot
from tests.generation.test_context_entities import mark, narrow_story, tight
from tests.generation.test_context_selection import settings
from tests.link_helpers import approve_links
from tests.generation.test_memory_kind import COAST, claim
from tests.storage.test_memory_entities_store import prepared, revision

FIELD='memory_entities'


def recorded(context):
    return [s for s in context.dependency_snapshot.selectors if s.field==FIELD]


def changed(repo,story_id,snapshot):
    return [c for c in compare_snapshot(repo.context_view(story_id),snapshot) if c.selector and c.selector.field==FIELD]


def with_event(repo,scene,journal,prose,*events):
    first=repo.list_scenes(scene.story_id)[0]
    extended=MemoryJournal(schema_version=4,source_prose_ids=[prose.id],events=[*journal.events,*events])
    memory=repo.save_version(scene.story_id,first.id,'memory',extended.model_dump_json(),[prose.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    approve_links(repo,scene.story_id)
    return extended


@pytest.mark.req('MEMORY-ENTITIES')
def test_fitting_request_records_no_entities_selector(tmp_path):
    repo,scene,journal,_,_=prepared(tmp_path)
    mark(repo,scene.story_id,{claim(journal,COAST):(['B'],[])})
    context=build_context(repo,scene.id,'brief',settings())
    assert recorded(context)==[]
    assert changed(repo,scene.story_id,context.dependency_snapshot)==[]


@pytest.mark.req('MEMORY-ENTITIES')
def test_selected_version_records_the_selector_and_goes_stale_on_a_mark(tmp_path):
    repo,scene,journal,_,_=prepared(tmp_path)
    selected=build_context(repo,scene.id,'brief',tight(repo,scene)).dependency_snapshot
    (selector,)=[s for s in selected.selectors if s.field==FIELD]
    assert selector.expected=={} and selector.owner_id==scene.id and selector.kind=='scene'
    assert changed(repo,scene.story_id,selected)==[]
    entities.apply_entity_marks(repo,scene.story_id,{claim(journal,COAST):(['B'],[])},revision(repo,scene.story_id))
    (change,)=changed(repo,scene.story_id,selected)
    assert change.current=={claim(journal,COAST):'[["B"],[]]'}


@pytest.mark.req('MEMORY-ENTITIES')
def test_narrowed_memory_stage_records_the_selector(tmp_path):
    from tests.generation.test_memory_stage_narrow import chars, role
    repo,scene,journal=narrow_story(tmp_path)
    full=build_context(repo,scene.id,'memory',role())
    narrowed=build_context(repo,scene.id,'memory',role(max_input_chars=chars(full)-500))
    assert 'narrow' in narrowed.memory_metrics
    assert len(recorded(narrowed))==1 and recorded(narrowed)[0].expected=={}
    assert recorded(full)==[]
    fact=claim(journal,'Скеля стоїть біля бухти')
    mark(repo,scene.story_id,{fact:(['A'],[])})
    (change,)=changed(repo,scene.story_id,narrowed.dependency_snapshot)
    assert change.current=={fact:'[["A"],[]]'}


@pytest.mark.req('MEMORY-ENTITIES')
def test_shadowed_model_mark_does_not_stale(tmp_path):
    repo,scene,journal,prose,_=prepared(tmp_path)
    event=_add_event('facts','Факт з учасником від події',prose.id,'вдома',901,participant_ids=['A'])
    with_event(repo,scene,journal,prose,event)
    selected=build_context(repo,scene.id,'brief',tight(repo,scene)).dependency_snapshot
    mark(repo,scene.story_id,{event.claim_id:(['B'],[])})
    assert repo.get_story(scene.story_id).memory_entities
    assert entities.entities_value(repo.context_view(scene.story_id),scene.id)=={}
    assert changed(repo,scene.story_id,selected)==[]


@pytest.mark.req('MEMORY-ENTITIES')
def test_author_mark_equal_to_the_event_does_not_stale(tmp_path):
    repo,scene,journal,prose,_=prepared(tmp_path)
    event=_add_event('facts','Факт з учасником від події',prose.id,'вдома',901,participant_ids=['A'])
    with_event(repo,scene,journal,prose,event)
    selected=build_context(repo,scene.id,'brief',tight(repo,scene)).dependency_snapshot
    repo.update_memory_entities(scene.story_id,event.claim_id,['A'],[],revision(repo,scene.story_id))
    assert entities.entities_value(repo.context_view(scene.story_id),scene.id)=={}
    assert changed(repo,scene.story_id,selected)==[]


@pytest.mark.req('MEMORY-ENTITIES')
def test_author_override_and_clearing_stale_the_version(tmp_path):
    repo,scene,journal,prose,_=prepared(tmp_path)
    event=_add_event('facts','Факт з учасником від події',prose.id,'вдома',901,participant_ids=['A'])
    with_event(repo,scene,journal,prose,event)
    sid=scene.story_id
    selected=build_context(repo,scene.id,'brief',tight(repo,scene)).dependency_snapshot
    repo.update_memory_entities(sid,event.claim_id,['B'],[],revision(repo,sid))
    (change,)=changed(repo,sid,selected)
    assert change.current=={event.claim_id:'[["B"],[]]'}
    # a model mark is cleared, an author one is not; a model mark over a participant-less record goes and comes back to {}
    target=claim(journal,COAST)
    repo.apply_entity_marks(sid,{target:(['A'],[])},revision(repo,sid))
    assert entities.entities_value(repo.context_view(sid),scene.id)[target]=='[["A"],[]]'
    repo.clear_entity_marks(sid,revision(repo,sid))
    assert target not in entities.entities_value(repo.context_view(sid),scene.id)
    repo.update_memory_entities(sid,event.claim_id,[],None,revision(repo,sid))
    assert entities.entities_value(repo.context_view(sid),scene.id)=={}
    assert changed(repo,sid,selected)==[]


@pytest.mark.req('MEMORY-ENTITIES')
def test_mark_of_a_claim_absent_before_the_scene_does_not_stale(tmp_path):
    repo,scene,journal,prose,_=prepared(tmp_path)
    first=repo.list_scenes(scene.story_id)[0]
    claim_id=claim(journal,COAST)
    entities.apply_entity_marks(repo,scene.story_id,{claim_id:(['B'],[])},revision(repo,scene.story_id))
    assert entities.entities_value(repo.context_view(scene.story_id),first.id)=={}
    assert entities.entities_value(repo.context_view(scene.story_id),scene.id)[claim_id]=='[["B"],[]]'


@pytest.mark.req('MEMORY-ENTITIES')
def test_old_snapshot_without_the_selector_is_not_compared(tmp_path):
    repo,scene,journal,_,_=prepared(tmp_path)
    selected=build_context(repo,scene.id,'brief',tight(repo,scene)).dependency_snapshot
    old=DependencySnapshot.model_validate({**selected.model_dump(),'selectors':[s.model_dump() for s in selected.selectors if s.field!=FIELD]})
    assert not any(s.field==FIELD for s in old.selectors)
    mark(repo,scene.story_id,{claim(journal,COAST):(['B'],[])})
    assert changed(repo,scene.story_id,old)==[]


@pytest.mark.req('MEMORY-ENTITIES')
def test_current_head_stays_fresh_while_its_snapshot_reports_the_change(tmp_path):
    # VALID-LINKS: a current head is judged by link fingerprints, which do not include the overlay.
    repo,scene,journal,_,_=prepared(tmp_path)
    context=build_context(repo,scene.id,'brief',tight(repo,scene))
    brief=repo.save_version(scene.story_id,scene.id,'brief','Бриф.',context.input_refs,dependency_snapshot=context.dependency_snapshot)
    repo.set_head(scene.id,'brief',brief.id,repo.get_scene(scene.id).revision)
    assert repo.get_version(brief.id).stale is False
    entities.apply_entity_marks(repo,scene.story_id,{claim(journal,COAST):(['B'],[])},revision(repo,scene.story_id))
    assert repo.get_version(brief.id).stale is False
    assert len(changed(repo,scene.story_id,context.dependency_snapshot))==1
