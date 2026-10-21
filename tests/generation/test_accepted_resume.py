import pytest
from storygen.domain import StoryCreate, SceneCreate, StageAttempt, new_id, RevisionConflict
from storygen.run_models import Run, RunRequest
from storygen.storage.repository import Repository
from storygen.generation.worker import RunCoordinator
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.authoring.blueprints import save_role_settings


def setup(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Продовження'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена',beats='Ранок'))
    for role in ['writer','editor','memory']:
        save_role_settings(repo,story.id,role,RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='patches'),repo.get_story(story.id).revision)
    request=RunRequest(story_id=story.id,scene_id=scene.id,mode='remaining')
    run=Run(id=new_id(),story_id=story.id,request_id='alternative',request=request,state='alternative',tasks=[{'scene_id':scene.id,'stage':'draft'},{'scene_id':scene.id,'stage':'edit'}])
    repo.enqueue_run(run)
    ref=repo.save_version(story.id,scene.id,'draft','Збережений текст',[])
    attempt=StageAttempt(id=new_id(),run_id=run.id,story_id=story.id,scene_id=scene.id,stage='draft',state='alternative',context={'run_cursor':0},partial_path='partial.txt',result_version_id=ref.id)
    repo.save_attempt(attempt)
    preview=repo.preview_acceptance(scene.id,ref.id)
    result=repo.accept_version(scene.id,ref.id,preview.expected_revision,preview.preview_fingerprint)
    return repo,run,scene,ref,attempt,result


def test_remaining_continues_after_accepted_result_without_inference_repeat(tmp_path):
    repo,run,scene,ref,attempt,result=setup(tmp_path)
    calls=[]
    worker=RunCoordinator(repo,lambda _: calls.append('inference'))
    resumed=worker.continue_after_acceptance(run.id,ref.id,0,result.scene.revision,result.acceptance.id)
    assert resumed.cursor==1 and resumed.state=='queued'
    assert calls==[]
    assert repo.get_attempt(attempt.id).state=='alternative'
    assert any(e.type=='continued_after_acceptance' and e.data['version_id']==ref.id for e in repo.list_run_events(run.id))
    with pytest.raises((ValueError,RevisionConflict)):
        worker.continue_after_acceptance(run.id,ref.id,0,result.scene.revision,result.acceptance.id)


@pytest.mark.parametrize('wrong',['version','cursor','revision','acceptance','task'])
def test_wrong_task_version_or_cursor_does_not_advance(tmp_path,wrong):
    repo,run,scene,ref,attempt,result=setup(tmp_path)
    if wrong=='task':
        run.tasks[0]['stage']='edit';repo.save_run(run)
    args=[run.id,ref.id,0,result.scene.revision,result.acceptance.id]
    if wrong=='version':args[1]='missing'
    if wrong=='cursor':args[2]=1
    if wrong=='revision':args[3]-=1
    if wrong=='acceptance':args[4]='other'
    with pytest.raises((ValueError,KeyError,RevisionConflict)):
        RunCoordinator(repo).continue_after_acceptance(*args)
    assert repo.get_run(run.id).cursor==0


def test_dependency_change_after_acceptance_blocks_continue(tmp_path):
    repo,run,scene,ref,attempt,result=setup(tmp_path)
    other=repo.create_scene(run.story_id,SceneCreate(title='Новий порядок'))
    with pytest.raises((ValueError,RevisionConflict)):
        RunCoordinator(repo).continue_after_acceptance(run.id,ref.id,0,result.scene.revision,result.acceptance.id)
    assert repo.get_run(run.id).cursor==0


@pytest.mark.parametrize('guard',['cancelled','refusal'])
def test_cancellation_or_refusal_block_cannot_be_bypassed(tmp_path,guard):
    repo,run,scene,ref,attempt,result=setup(tmp_path)
    worker=RunCoordinator(repo)
    if guard=='cancelled':worker.cancel(run.id)
    else:
        from storygen.evaluation.story_adapter import EvaluationSettings,save_evaluation_settings
        from storygen.evaluation.models import EvaluatorConfig,FailureDetail
        from storygen.evaluation.blocks import block_evaluator
        config=EvaluatorConfig(provider='local',model='judge',max_input_chars=100000)
        # Server-installed pause policy, synthetic fixture independent of real calibration.
        settings=EvaluationSettings(config=config).model_dump();settings['policy']='pause_on_failure'
        repo.write_evaluator_settings(run.story_id,settings)
        block_evaluator(repo,run.story_id,config,FailureDetail(category='refusal_content',message='Контентна відмова'),run.id,attempt.id)
        run.tasks.append({'scene_id':scene.id,'stage':'evaluate'});repo.save_run(run)
    with pytest.raises((ValueError,RevisionConflict)):
        worker.continue_after_acceptance(run.id,ref.id,0,result.scene.revision,result.acceptance.id)
    assert repo.get_run(run.id).cursor==0


def test_fresh_selected_alternative_continues_without_acceptance_record(tmp_path):
    repo,run,scene,ref,attempt,result=setup(tmp_path)
    fresh=repo.save_version(run.story_id,scene.id,'draft','Інша свіжа альтернатива',[])
    selected=repo.set_head(scene.id,'draft',fresh.id,result.scene.revision)
    attempt.result_version_id=fresh.id;repo.save_attempt(attempt)
    resumed=RunCoordinator(repo).continue_after_acceptance(run.id,fresh.id,0,selected.revision)
    assert resumed.cursor==1 and resumed.state=='queued'
    assert repo.list_acceptances(run.story_id,fresh.id)==[]
