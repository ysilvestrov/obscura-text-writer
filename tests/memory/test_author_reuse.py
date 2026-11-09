import threading
import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.memory.models import MemorySnapshot, MemoryEntry
from storygen.providers.models import RoleSettings, ProviderSettings
from tests.memory.wire_helpers import v4_answer
from storygen.providers.streaming import GenerationEvent
from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage


def workspace(tmp_path, changed=False):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Нейтральна пам’ять'))
    first=repo.create_scene(story.id,SceneCreate(title='Бібліотека'))
    second=repo.create_scene(story.id,SceneCreate(title='Парк'))
    old=repo.save_version(story.id,first.id,'manual','Олена взяла книжку.',[])
    repo.set_head(first.id,'prose',old.id,repo.get_scene(first.id).revision)
    memory=repo.save_version(story.id,first.id,'memory',MemorySnapshot(source_prose_ids=[old.id],facts=[MemoryEntry(text='Олена має книжку',quote='Олена взяла книжку.',source_version_id=old.id)]).model_dump_json(),[old.id])
    repo.set_head(first.id,'memory',memory.id,repo.get_scene(first.id).revision)
    new=repo.save_version(story.id,first.id,'manual','Олена повернула книжку.' if changed else 'Олена взяла книжку.',[])
    repo.set_head(first.id,'prose',new.id,repo.get_scene(first.id).revision)
    current=repo.save_version(story.id,second.id,'manual','Олена вийшла до парку.',[])
    repo.set_head(second.id,'prose',current.id,repo.get_scene(second.id).revision)
    role=RoleSettings(provider=ProviderSettings(model='fake'),memory_mode='evidence_delta',context_tokens=64000)
    return repo,first,second,old,new,memory,role


@pytest.mark.parametrize('changed',[False,True])
def test_historical_memory_requires_exact_author_approval(tmp_path,changed):
    from storygen.memory.reuse import memory_for_update, MemoryApprovalRequired
    repo,first,scene,old,new,memory,role=workspace(tmp_path,changed)
    with pytest.raises(MemoryApprovalRequired) as caught:
        memory_for_update(repo.context_view(scene.story_id),scene.id)
    review=caught.value.review
    assert review['changed_text_count']==int(changed)
    assert review['changed_version_count']==1
    previous,approval,provenance=memory_for_update(repo.context_view(scene.story_id),scene.id,review['fingerprint'])
    assert previous.source_prose_ids==[old.id]
    assert previous.events[0].source_version_id==old.id
    assert previous.events[0].quote=='Олена взяла книжку.'
    assert approval['memory_id']==memory.id and provenance
    with pytest.raises(ValueError,match='підтвердження'):
        memory_for_update(repo.context_view(scene.story_id),scene.id,'0'*64)
    replacement=repo.save_version(scene.story_id,scene.id,'manual','Інший поточний текст.',[])
    repo.set_head(scene.id,'prose',replacement.id,repo.get_scene(scene.id).revision)
    with pytest.raises(ValueError,match='підтвердження'):
        memory_for_update(repo.context_view(scene.story_id),scene.id,review['fingerprint'])


def test_approved_update_publishes_and_preserves_provenance_for_next_scene(tmp_path):
    from storygen.memory.reuse import MemoryApprovalRequired
    from storygen.memory.service import journal_before
    repo,first,scene,old,new,memory,role=workspace(tmp_path,True)
    with pytest.raises(MemoryApprovalRequired) as caught:
        build_context(repo,scene.id,'memory',role)
    context=build_context(repo,scene.id,'memory',role,memory_approval=caught.value.review['fingerprint'])
    assert memory.id in context.dependency_snapshot.accepted_stale_memory_ids
    assert context.context_warnings
    class Gateway:
        def stream(self,context,cancel):
            yield GenerationEvent(type='delta',text=v4_answer(context))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'memory',context,Gateway(),threading.Event(),lambda text:None)
    assert attempt.state=='completed',attempt.error
    result=repo.get_version(attempt.result_version_id)
    assert not result.stale and result.dependency_snapshot.memory_provenance
    from storygen.memory.service import save_scene_memory
    manual=save_scene_memory(repo,scene.id,repo.read_text(result.id)+'\n',repo.get_scene(scene.id).revision)
    assert manual.dependency_snapshot.memory_provenance
    assert memory.id in manual.dependency_snapshot.accepted_stale_memory_ids
    assert not repo.get_version(manual.id).stale
    from storygen.storage.integrity import check_integrity
    assert not [i for i in check_integrity(repo.root).issues if i.code=='invalid_memory']
    third=repo.create_scene(scene.story_id,SceneCreate(title='Вечір'))
    past=journal_before(repo,third.id)
    assert past.source_prose_ids[0]==old.id and past.events[0].quote=='Олена взяла книжку.'
    assert repo.get_version(memory.id).stale,'Author approval must not clear the old stale flag'


@pytest.mark.parametrize('source_kind',['future','foreign'])
def test_future_or_foreign_sources_cannot_be_confirmed(tmp_path,source_kind):
    from storygen.memory.reuse import memory_for_update, MemoryApprovalRequired
    repo,first,scene,old,new,memory,role=workspace(tmp_path)
    future=repo.get_scene(scene.id).heads['prose']
    if source_kind=='foreign':
        other=repo.create_story(StoryCreate(title='Інший твір'))
        other_scene=repo.create_scene(other.id,SceneCreate(title='Інша сцена'))
        future=repo.save_version(other.id,other_scene.id,'manual','Сторонній текст.',[]).id
    bad=repo.save_version(scene.story_id,first.id,'memory',MemorySnapshot(source_prose_ids=[future]).model_dump_json(),[] if source_kind=='foreign' else [future])
    repo.set_head(first.id,'memory',bad.id,repo.get_scene(first.id).revision)
    with pytest.raises(ValueError) as caught:
        memory_for_update(repo.context_view(scene.story_id),scene.id)
    assert not isinstance(caught.value,MemoryApprovalRequired)


def test_queue_never_enqueues_unconfirmed_memory_or_bypasses_context_limits(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.worker import RunCoordinator,RunRequest
    from storygen.generation.readiness import preview
    repo,first,scene,old,new,memory,role=workspace(tmp_path,True)
    for name in ['planner','writer','editor','memory']:
        save_role_settings(repo,scene.story_id,name,role,repo.get_story(scene.story_id).revision)
    worker=RunCoordinator(repo,lambda _:pytest.fail('No model calls during preflight'))
    request=RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='stage',stage='memory')
    before=repo.read_text(memory.id)
    preflight=preview(repo,request)
    assert not preflight['ready'] and preflight['can_confirm']
    with pytest.raises(ValueError,match='підтвердження'):worker.enqueue(request,'declined')
    assert not worker.list_runs(scene.story_id)
    token=preflight['memory_review']['fingerprint']
    accepted=request.model_copy(update={'memory_approval':token})
    assert preview(repo,accepted)['ready']
    run=worker.enqueue(accepted,'approved')
    assert run.request.memory_approval==token
    assert repo.read_text(memory.id)==before
    with pytest.raises(ValueError):
        RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='remaining',memory_approval=token)
    tiny=role.model_copy(update={'context_tokens':512,'max_output_tokens':500})
    save_role_settings(repo,scene.story_id,'memory',tiny,repo.get_story(scene.story_id).revision)
    limited=preview(repo,request)
    assert not limited['ready'] and not limited.get('can_confirm')


def test_new_inputs_during_generation_keep_result_as_alternative(tmp_path):
    from storygen.memory.reuse import MemoryApprovalRequired
    repo,first,scene,old,new,memory,role=workspace(tmp_path,True)
    with pytest.raises(MemoryApprovalRequired) as caught:build_context(repo,scene.id,'memory',role)
    context=build_context(repo,scene.id,'memory',role,memory_approval=caught.value.review['fingerprint'])
    class Gateway:
        def stream(self,context,cancel):
            replacement=repo.save_version(scene.story_id,first.id,'manual','Прозу знову змінено.',[])
            repo.set_head(first.id,'prose',replacement.id,repo.get_scene(first.id).revision)
            yield GenerationEvent(type='delta',text=v4_answer(context))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'memory',context,Gateway(),threading.Event(),lambda _:None)
    assert attempt.state=='alternative'
    assert 'memory' not in repo.get_scene(scene.id).heads
