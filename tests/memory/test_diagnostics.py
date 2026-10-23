import json
import threading
import pytest
from pydantic import ValidationError
from storygen.memory.journal import MemoryOperations


def test_scope_error_names_operation_without_echoing_payload():
    from storygen.memory.diagnostics import memory_error
    rows=[dict(action='add',category='character_states',text='private text',evidence_id='f000001') for _ in range(8)]
    rows.append(dict(action='add',category='open_threads',text='private text',character_ids=['private-id'],evidence_id='f000001'))
    with pytest.raises(ValidationError) as caught:MemoryOperations.model_validate({'operations':rows})
    message=memory_error(caught.value)
    assert '9' in message and 'character_ids' in message
    assert 'private' not in message


def test_unknown_error_and_extra_fields_cannot_echo_documents():
    from storygen.memory.diagnostics import memory_error
    assert 'private' not in memory_error(ValueError('private secret echo'))
    with pytest.raises(ValidationError) as caught:MemoryOperations.model_validate({'private secret key':'private text'})
    assert 'private' not in memory_error(caught.value)
    assert 'JSON' in memory_error(json.JSONDecodeError('private text','private document',0))


@pytest.mark.parametrize('category,expected_error',[('facts','Невідомий фрагмент'),([], 'category'),({}, 'category')])
def test_stage_preserves_partial_and_specific_evidence_failure(tmp_path,category,expected_error):
    from storygen.domain import StoryCreate,SceneCreate
    from storygen.storage.repository import Repository
    from storygen.providers.models import RoleSettings,ProviderSettings
    from storygen.providers.streaming import GenerationEvent
    from storygen.generation.context import build_context
    from storygen.generation.stages import execute_stage
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Synthetic'))
    scene=repo.create_scene(story.id,SceneCreate(title='Scene'))
    prose=repo.save_version(story.id,scene.id,'manual','Synthetic prose.',[])
    repo.set_head(scene.id,'prose',prose.id,scene.revision)
    role=RoleSettings(provider=ProviderSettings(model='fake'),memory_mode='evidence_delta',context_tokens=32768)
    context=build_context(repo,scene.id,'memory',role)
    raw=json.dumps({'schema_version':2,'operations':[dict(action='add',category=category,text='Claim',evidence_id='f999999')]})
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    attempt=execute_stage(repo,scene.id,'memory',context,Gateway(),threading.Event(),lambda _:None)
    assert attempt.state=='failed'
    assert expected_error in attempt.error
    assert repo.files.read_partial(attempt.partial_path)==raw
    assert not repo.get_scene(scene.id).heads.get('memory')


@pytest.mark.parametrize('category',['facts','timeline','open_threads'])
def test_only_redundant_nonstate_scope_is_normalized(category):
    from storygen.memory.journal import parse_memory_result,MemoryJournal
    raw=json.dumps({'schema_version':2,'operations':[dict(action='add',category=category,text='Claim',character_ids=['A'],evidence_id='f000001')]})
    warnings=[]
    journal=parse_memory_result(raw,MemoryJournal(),'p','Evidence.', 'evidence_delta',['A'],warnings=warnings)
    assert journal.events[0].character_ids==[] and journal.events[0].text=='Claim'
    assert len(warnings)==1 and '1' in warnings[0] and category in warnings[0]
    assert json.loads(raw)['operations'][0]['character_ids']==['A']


def test_scope_normalization_never_bypasses_evidence_or_character_validation():
    from storygen.memory.journal import parse_memory_result,MemoryJournal
    row=dict(action='add',category='open_threads',text='Claim',character_ids=['A'],evidence_id='f999999')
    with pytest.raises(ValueError,match='Невідомий фрагмент'):
        parse_memory_result(json.dumps({'schema_version':2,'operations':[row]}),MemoryJournal(),'p','Evidence.','evidence_delta',['A'])
    row.update(category='character_states',evidence_id='f000001',character_ids=['unknown'])
    with pytest.raises(ValueError,match='Невідомий scope'):
        parse_memory_result(json.dumps({'schema_version':2,'operations':[row]}),MemoryJournal(),'p','Evidence.','evidence_delta',['A'])


def test_normalization_warning_survives_run_reload(tmp_path):
    from storygen.domain import StoryCreate,SceneCreate
    from storygen.storage.repository import Repository
    from storygen.providers.models import RoleSettings,ProviderSettings
    from storygen.providers.streaming import GenerationEvent
    from storygen.generation.worker import RunCoordinator
    from storygen.run_models import RunRequest
    from storygen.authoring.blueprints import save_role_settings
    from storygen.memory.journal import load_memory
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Synthetic'))
    scene=repo.create_scene(story.id,SceneCreate(title='Scene',character_ids=['A']))
    prose=repo.save_version(story.id,scene.id,'manual','Synthetic evidence.',[])
    repo.set_head(scene.id,'prose',prose.id,scene.revision)
    role=RoleSettings(provider=ProviderSettings(model='fake'),context_tokens=32768,memory_mode='evidence_delta')
    save_role_settings(repo,story.id,'memory',role,repo.get_story(story.id).revision)
    raw=json.dumps({'schema_version':2,'operations':[dict(action='add',category='open_threads',text='Question',character_ids=['A'],evidence_id='f000001')]})
    class Gateway:
        def stream(self,*_):
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='memory'),'warning')
    worker._execute(run.id)
    stored=Repository(tmp_path)
    finished=stored.get_run(run.id)
    assert finished.state=='completed' and 'character_ids' in finished.warning
    attempt=stored.list_attempts(story.id,run.id)[0]
    assert len(attempt.context['memory_warnings'])==1
    assert stored.files.read_partial(attempt.partial_path)==raw
    memory=load_memory(stored.read_text(stored.get_scene(scene.id).heads['memory']))
    assert memory.events[0].character_ids==[]
