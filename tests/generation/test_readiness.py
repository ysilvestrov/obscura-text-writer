import pytest

from storygen.authoring.blueprints import save_role_settings
from storygen.domain import StoryCreate, SceneCreate
from storygen.generation.worker import RunCoordinator, RunRequest
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.storage.repository import Repository


def setup_story(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Готовність'))
    scene=repo.create_scene(story.id,SceneCreate(title='Початок',beats='Початок історії'))
    for role in ['planner','writer','editor','memory']:
        save_role_settings(repo,story.id,role,RoleSettings(provider=ProviderSettings(model=role)),repo.get_story(story.id).revision)
    return repo,story,scene,RunCoordinator(repo)


def test_invalid_stage_is_rejected_before_queue_and_model_call(tmp_path):
    repo,story,scene,worker=setup_story(tmp_path)
    with pytest.raises(ValueError,match='попередній етап'):
        worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='draft'),'missing')
    assert worker.list_runs()==[]


def test_scene_preflight_allows_outputs_produced_by_earlier_tasks(tmp_path):
    repo,story,scene,worker=setup_story(tmp_path)
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='scene'),'whole')
    assert [task['stage'] for task in run.tasks]==['brief','draft','edit','memory']


def test_preflight_requires_all_roles_used_but_single_stage_only_one(tmp_path):
    repo,story,scene,worker=setup_story(tmp_path)
    with repo.db.connection() as db:
        db.execute("DELETE FROM role_settings WHERE story_id=? AND role='writer'",(story.id,))
    worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='brief'),'one')
    with pytest.raises(ValueError,match='writer'):
        worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='scene'),'whole')


def test_readiness_reports_only_requested_roles_and_rebuild_missing_prose(tmp_path):
    repo,story,scene,worker=setup_story(tmp_path)
    result=worker.readiness(story.id,scene.id)
    assert list(result['operations']['prepare']['roles'])==['planner']
    assert list(result['operations']['memory']['roles'])==['memory']
    assert result['operations']['brief']['ready']
    assert not result['operations']['draft']['ready']
    assert not result['operations']['rebuild_memory']['ready']


def test_idempotent_replay_returns_existing_run_after_inputs_change(tmp_path):
    repo,story,scene,worker=setup_story(tmp_path)
    request=RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='brief')
    first=worker.enqueue(request,'same')
    with repo.db.connection() as db:
        db.execute('DELETE FROM role_settings WHERE story_id=?',(story.id,))
    assert worker.enqueue(request,'same').id==first.id


def test_stale_selected_input_is_rejected_before_queue(tmp_path):
    repo,story,scene,worker=setup_story(tmp_path)
    brief=repo.save_version(story.id,scene.id,'brief','Завдання',[])
    repo.set_head(scene.id,'brief',brief.id,scene.revision)
    with repo.db.connection() as db:
        brief.stale=True
        db.execute('UPDATE versions SET payload=? WHERE id=?',(brief.model_dump_json(),brief.id))
    with pytest.raises(ValueError,match='застарілий'):
        worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='draft'),'stale')
    assert worker.list_runs()==[]


def test_disabled_evaluator_skips_previously_queued_task_without_gateway(tmp_path):
    from storygen.evaluation.models import EvaluatorConfig
    from storygen.evaluation.story_adapter import EvaluationSettings, save_evaluation_settings
    repo,story,scene,worker=setup_story(tmp_path)
    settings=EvaluationSettings(config=EvaluatorConfig(provider='local',model='judge',max_input_chars=10000),policy='report')
    save_evaluation_settings(repo,story.id,settings)
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='scene'),'auto')
    run.cursor=len(run.tasks)-1;run.state='running';worker._save(run)
    save_evaluation_settings(repo,story.id,settings.model_copy(update={'policy':'off'}))
    def forbidden(_):raise AssertionError('Disabled evaluator must never create a gateway')
    worker.evaluator_factory=forbidden
    worker._evaluate(run)
    assert worker.get_run(run.id).cursor==len(run.tasks)
    assert worker.list_events(run.id)[-1].type=='evaluation_skipped'


def test_prepare_requires_authored_sources_and_brief_requires_scene_plan(tmp_path):
    repo,story,scene,worker=setup_story(tmp_path)
    assert not worker.readiness(story.id,scene.id)['operations']['prepare']['ready']
    empty=repo.create_scene(story.id,SceneCreate(title='Без плану'))
    result=worker.readiness(story.id,empty.id)['operations']['brief']
    assert not result['ready'] and 'план' in result['reason']


def test_resume_preflight_checks_pending_roles_only(tmp_path):
    repo,story,scene,worker=setup_story(tmp_path)
    run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='scene'),'pending')
    run.state='paused';worker._save(run)
    with repo.db.connection() as db:
        db.execute("DELETE FROM role_settings WHERE story_id=? AND role='memory'",(story.id,))
    with pytest.raises(ValueError,match='memory'):
        worker.resume(run.id)
    assert worker.get_run(run.id).state=='paused'
