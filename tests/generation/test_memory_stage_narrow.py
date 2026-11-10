"""MEMORY-SELECT-S07 in the request: the memory stage narrows its catalog only on overflow, with matching bounds (#60)."""
import json

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import ContextOverflow, build_context
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository


def role(**update):
    return RoleSettings(**{'provider':ProviderSettings(model='fake'),'memory_mode':'evidence_delta','context_tokens':262144,**update})


def story(tmp_path):
    repo=Repository(tmp_path);item=repo.create_story(StoryCreate(title='Каталог'))
    first,second=(repo.create_scene(item.id,SceneCreate(title=t,beats='Вдома',character_ids=cast)) for t,cast in (('1',['A','B']),('2',['A'])))
    p1=repo.save_version(item.id,first.id,'manual','Анна і Борис удома.',[])
    repo.set_head(first.id,'prose',p1.id,repo.get_scene(first.id).revision)
    events=[_add_event('character_states','Анна втомлена',p1.id,'удома',0,['A']),_add_event('character_states','Іде дощ',p1.id,'удома',0)]
    events+=[_add_event('character_states',f'Борис тримає річ номер {n} у старій шафі на горищі',p1.id,'удома',n,['B']) for n in range(40)]
    journal=MemoryJournal(schema_version=3,source_prose_ids=[p1.id],events=events)
    memory=repo.save_version(item.id,first.id,'memory',journal.model_dump_json(),[p1.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    p2=repo.save_version(item.id,second.id,'manual','Анна дивиться на дощ.',[])
    repo.set_head(second.id,'prose',p2.id,repo.get_scene(second.id).revision)
    return repo,repo.get_scene(second.id)


def chars(context):
    return len(context.system_text)+len(context.user_text)


def test_fitting_memory_stage_is_unchanged(tmp_path):
    repo,scene=story(tmp_path)
    context=build_context(repo,scene.id,'memory',role())
    assert context.memory_metrics['projection_version']=='memory-catalog-v4' and 'narrow' not in context.memory_metrics
    assert len(json.loads(context.fragments['memory_schema_bounds'])['mutable']['character_states'])==42
    assert not any('Каталог пам’яті звужено' in w for w in context.context_warnings)


def test_overflowing_memory_stage_narrows_catalog_and_bounds(tmp_path):
    repo,scene=story(tmp_path)
    full=build_context(repo,scene.id,'memory',role())
    context=build_context(repo,scene.id,'memory',role(max_input_chars=chars(full)-500))
    assert chars(context)<=chars(full)-500
    assert context.memory_metrics['projection_version']=='memory-catalog-v4-narrow'
    assert context.memory_metrics['narrow']['hidden']==40 and context.memory_metrics['catalog_chars']<full.memory_metrics['catalog_chars']
    mutable=json.loads(context.fragments['memory_schema_bounds'])['mutable']['character_states']
    assert len(mutable)==2 and 'Борис тримає річ' not in context.user_text
    assert any('Каталог пам’яті звужено: 40 записів' in w for w in context.context_warnings)


def test_narrowed_catalog_that_still_overflows_is_an_error(tmp_path):
    repo,scene=story(tmp_path)
    with pytest.raises(ContextOverflow):
        build_context(repo,scene.id,'memory',role(max_input_chars=500))
