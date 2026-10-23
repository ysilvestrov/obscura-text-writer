import json

import pytest

from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.providers.streaming import GenerationEvent
from storygen.authoring.blueprints import save_role_settings
from storygen.generation.worker import RunCoordinator
from storygen.run_models import RunRequest
from storygen.generation.copyedit_review import copyedit_preview, select_copyedits


def setup_workflow(tmp_path, mode='patches', no_changes=False,limit=3):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Дві сцени'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=f'Сцена {i}',beats=f'Подія {i}')) for i in range(2)]
    for name in ['planner','writer','editor','memory']:
        save_role_settings(repo,story.id,name,RoleSettings(provider=ProviderSettings(model=name),edit_mode=mode,memory_mode='evidence_delta'),repo.get_story(story.id).revision)
    calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            position=repo.get_scene(ctx.scene_id).position
            if ctx.stage=='edit':
                changed='відчинив' in ctx.user_text and not no_changes
                raw=json.dumps({'edits':[dict(fragment_id='f000001',original='відчинив',replacement='відчинила',category='grammar')] if changed else []}) if mode=='patches' else f'Олена відчинила двері номер {position}.'
            else:
                raw={'brief':json.dumps({'objective':'Сцена','beats':['Подія']}),'draft':f'Олена відчинив двері номер {position}.','memory':json.dumps({'facts':[{'text':f'Подія {position}.','evidence_id':'f000001'}]})}[ctx.stage]
            yield GenerationEvent(type='delta',text=raw)
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker=RunCoordinator(repo,lambda _:Gateway())
    request=RunRequest(story_id=story.id,scene_id=scenes[0].id,mode='remaining',edit_workflow='loop',edit_pass_limit=limit)
    run=worker.enqueue(request,'workflow')
    return repo,scenes,worker,run,calls


@pytest.mark.parametrize('mode',['patches','diff','prose'])
def test_two_scenes_wait_for_one_review_each_then_continue_memory(tmp_path,mode):
    repo,scenes,worker,run,calls=setup_workflow(tmp_path,mode)
    for index,scene in enumerate(scenes):
        worker._execute(run.id)
        current=worker.get_run(run.id)
        assert current.state=='needs_review',current.error
        assert current.cursor==index*4+2
        assert 'prose' not in repo.get_scene(scene.id).heads
        checkpoint=current.editor_loops[str(current.cursor)]
        assert checkpoint['attempt_count']==2
        preview=copyedit_preview(repo,scene.id,checkpoint['proposal_attempt_id'])
        result=select_copyedits(repo,scene.id,checkpoint['proposal_attempt_id'],list(range(len(preview['edits']))),preview['expected_revision'],preview['proposal_fingerprint'])
        assert result['run'].state=='needs_review'
        assert worker.get_run(run.id).cursor==current.cursor
        worker.continue_after_acceptance(run.id,result['version'].id,current.cursor,result['scene'].revision)
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed'
    assert len([c for c in calls if c.stage=='edit'])==4
    assert len(worker.get_run(run.id).editor_loops)==2
    memory=json.loads(repo.read_text(repo.get_scene(scenes[-1].id).heads['memory']))
    assert len(memory['source_prose_ids'])==2


def test_initial_noop_does_not_create_prose_or_run_memory(tmp_path):
    repo,scenes,worker,run,calls=setup_workflow(tmp_path,no_changes=True)
    worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='failed'
    assert 'змін' in current.error
    assert [c.stage for c in calls]==['brief','draft','edit']
    assert 'prose' not in repo.get_scene(scenes[0].id).heads
    assert not current.editor_loops['2']['proposal_attempt_id']


def test_workflow_failed_second_pass_offers_first_and_waits_for_acceptance(tmp_path):
    repo,scenes,worker,run,calls=setup_workflow(tmp_path)
    original=worker.gateway_factory
    class FailSecond:
        def stream(self,ctx,cancel):
            if ctx.stage=='edit' and any(c.stage=='edit' for c in calls):
                calls.append(ctx)
                yield GenerationEvent(type='error',finish_reason='length',message='Ліміт reasoning')
            else:yield from original(ctx.settings.provider).stream(ctx,cancel)
    worker.gateway_factory=lambda _:FailSecond()
    worker._execute(run.id);current=worker.get_run(run.id)
    assert current.state=='needs_review' and current.cursor==2
    checkpoint=current.editor_loops['2']
    assert checkpoint['stop_reason']=='pass_failed' and checkpoint['attempt_count']==2
    assert not any(c.stage=='memory' for c in calls)
    p=copyedit_preview(repo,scenes[0].id,checkpoint['proposal_attempt_id'])
    result=select_copyedits(repo,scenes[0].id,checkpoint['proposal_attempt_id'],list(range(len(p['edits']))),p['expected_revision'],p['proposal_fingerprint'])
    assert result['run'].state=='needs_review' and worker.get_run(run.id).cursor==2


def test_workflow_limit_one_and_readiness_count(tmp_path):
    repo,scenes,worker,run,calls=setup_workflow(tmp_path,limit=1)
    preview=worker.readiness(run.story_id,scenes[0].id)['operations']['remaining']
    assert preview['calls']==16 and preview['edit_loop_scenes']==2
    worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='needs_review'
    assert current.editor_loops['2']['stop_reason']=='limit'
    assert len([c for c in calls if c.stage=='edit'])==1


def test_workflow_saved_pass_recovery_has_no_duplicate_call(tmp_path,monkeypatch):
    from storygen.generation import stages
    repo,scenes,worker,run,calls=setup_workflow(tmp_path)
    original=stages.execute_stage
    def crash(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('crash after saved pass')
    monkeypatch.setattr(stages,'execute_stage',crash)
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='failed'
    assert len([c for c in calls if c.stage=='edit'])==1
    monkeypatch.setattr(stages,'execute_stage',original)
    worker.resume(run.id)
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='needs_review'
    assert len([c for c in calls if c.stage=='edit'])==2


def test_workflow_uses_draft_instead_of_previous_prose(tmp_path):
    repo,scenes,worker,run,calls=setup_workflow(tmp_path)
    ref=repo.save_version(run.story_id,scenes[0].id,'manual','Стара проза.',[])
    repo.set_head(scenes[0].id,'prose',ref.id,repo.get_scene(scenes[0].id).revision)
    worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='needs_review',current.error
    assert 'Стара проза.' not in next(c for c in calls if c.stage=='edit').user_text
    assert 'відчинив' in next(c for c in calls if c.stage=='edit').user_text
    assert repo.get_scene(scenes[0].id).heads['prose']==ref.id


def test_workflow_pause_between_passes_keeps_task_cursor(tmp_path):
    repo,scenes,worker,run,calls=setup_workflow(tmp_path)
    run.request.pause_after=['edit'];worker._save(run)
    worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='paused' and current.cursor==2
    assert current.editor_loops['2']['pass_cursor']==1
    assert current.editor_loops['2']['attempt_count']==1
    assert worker.run_readiness(run.id)['calls']==9
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='needs_review'
    assert len([c for c in calls if c.stage=='edit'])==2


def test_standalone_prose_keeps_full_context_and_working_text(tmp_path):
    repo,scenes,worker,run,calls=setup_workflow(tmp_path,mode='prose')
    # Build the writer's brief/draft first using the ordinary persisted tasks.
    run.request.pause_after=['draft'];worker._save(run);worker._execute(run.id)
    scene=repo.get_scene(scenes[0].id)
    standalone=worker.enqueue(RunRequest(story_id=run.story_id,scene_id=scene.id,mode='edit_loop'), 'standalone-prose')
    worker._execute(standalone.id)
    edits=[c for c in calls if c.stage=='edit']
    assert len(edits)==2
    assert 'ЗАВДАННЯ ПИСЬМЕННИКУ' in edits[0].user_text
    assert 'Олена відчинив' in edits[0].user_text
    assert 'Олена відчинила' in edits[1].user_text
    assert worker.get_run(standalone.id).state=='needs_review'
    assert 'prose' not in repo.get_scene(scene.id).heads


@pytest.mark.parametrize('pause_in_stream',[False,True])
def test_noop_with_selected_identical_prose_preserves_pause(tmp_path,pause_in_stream):
    repo,scenes,worker,run,calls=setup_workflow(tmp_path,no_changes=True)
    run.request.pause_after=['draft'];worker._save(run);worker._execute(run.id)
    scene=repo.get_scene(scenes[0].id)
    ref=repo.save_version(run.story_id,scene.id,'manual',repo.read_text(scene.heads['draft']),[])
    repo.set_head(scene.id,'prose',ref.id,scene.revision)
    current=worker.get_run(run.id);current.request.pause_after=[] if pause_in_stream else ['edit'];worker._save(current)
    if pause_in_stream:
        factory=worker.gateway_factory
        class PauseGateway:
            def stream(self,ctx,cancel):
                if ctx.stage=='edit':worker.pause(run.id)
                yield from factory(None).stream(ctx,cancel)
        worker.gateway_factory=lambda _:PauseGateway()
    worker.resume(run.id);worker._execute(run.id)
    current=worker.get_run(run.id)
    assert current.state=='paused' and current.cursor==3
    assert [c.stage for c in calls]==['brief','draft','edit']


def test_local_summary_recovery_does_not_require_new_editor_configuration(tmp_path,monkeypatch):
    from storygen.generation import stages
    repo,scenes,worker,run,calls=setup_workflow(tmp_path,limit=1)
    original=stages.execute_stage
    def crash(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('saved final pass')
    monkeypatch.setattr(stages,'execute_stage',crash)
    worker._execute(run.id)
    role=RoleSettings(provider=ProviderSettings(model='changed'),max_input_chars=1)
    save_role_settings(repo,run.story_id,'editor',role,repo.get_story(run.story_id).revision)
    assert worker.run_readiness(run.id)['ready']
    worker.resume(run.id);worker._execute(run.id)
    assert worker.get_run(run.id).state=='needs_review'
    assert len([c for c in calls if c.stage=='edit'])==1
