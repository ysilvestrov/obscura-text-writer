import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.generation.context import build_context, ContextOverflow
from storygen.memory.models import MemorySnapshot, MemoryEntry
from storygen.memory.service import memory_before


def setup(repo):
    story=repo.create_story(StoryCreate(title='Твір'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i),beats=f'Майбутнє {i}')) for i in range(3)]
    return story,scenes


def test_scene_two_sees_only_committed_past(tmp_path):
    repo=Repository(tmp_path);story,scenes=setup(repo)
    prose=repo.save_version(story.id,scenes[0].id,'manual','Минуле сталося',[])
    repo.set_head(scenes[0].id,'prose',prose.id,0)
    rejected=repo.save_version(story.id,scenes[0].id,'edited','Відкинута подія',[])
    memory=MemorySnapshot(facts=[MemoryEntry(text='Минуле',source_version_id=prose.id,quote='Минуле')],source_prose_ids=[prose.id])
    ref=repo.save_version(story.id,scenes[0].id,'memory',memory.model_dump_json(),[prose.id])
    repo.set_head(scenes[0].id,'memory',ref.id,1)
    context=build_context(repo,scenes[1].id,'brief',RoleSettings(provider=ProviderSettings(model='test')))
    assert 'Відкинута' not in context.user_text
    assert prose.id in context.input_refs and rejected.id not in context.input_refs
    assert 'МАЙБУТНІ ПОДІЇ' in context.user_text
    assert memory_before(repo,scenes[1].id).facts[0].text=='Минуле'
    repo.set_head(scenes[0].id,'prose',rejected.id,2)
    with pytest.raises(ValueError,match='пам’ять'): memory_before(repo,scenes[1].id)


def test_budget_overflow_is_explicit(tmp_path):
    repo=Repository(tmp_path);story,scenes=setup(repo)
    scene=scenes[0]
    from storygen.authoring.service import update_scene_plan
    update_scene_plan(repo,scene.id,'дуже довгий текст '*2000,0)
    with pytest.raises(ContextOverflow) as exc:
        build_context(repo,scene.id,'brief',RoleSettings(provider=ProviderSettings(model='x'),context_tokens=1024,max_output_tokens=512))
    assert exc.value.estimated_tokens>512
