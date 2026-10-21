import threading
import time
import pytest
from storygen.domain import StoryCreate, SceneCreate, RevisionConflict
from storygen.storage.repository import Repository
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.generation.worker import RunCoordinator, RunRequest, AppInstanceLock


def ready(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Черга'));scene=repo.create_scene(story.id,SceneCreate(title='Сцена',beats='Ранок у бібліотеки'))
    for role in ['planner','writer','editor','memory']:
        story=save_role_settings(repo,story.id,role,RoleSettings(provider=ProviderSettings(model=role)),repo.get_story(story.id).revision)
    return repo,story,scene


def wait_until(predicate):
    end=time.monotonic()+5
    while time.monotonic()<end:
        if predicate(): return
        time.sleep(.01)
    raise AssertionError('worker did not reach expected state')


class BlockingGateway:
    def __init__(self):self.entered=threading.Event();self.release=threading.Event();self.calls=0;self.active=0;self.maximum=0
    def stream(self,context,cancel):
        self.calls+=1;self.active+=1;self.maximum=max(self.maximum,self.active);self.entered.set()
        self.release.wait(3)
        self.active-=1
        if cancel.is_set(): yield GenerationEvent(type='cancelled');return
        yield GenerationEvent(type='delta',text='{"objective":"Ранок","beats":["Студія"]}')
        yield GenerationEvent(type='terminal',finish_reason='stop')


def test_repeated_request_id_returns_same_run(tmp_path):
    repo,story,scene=ready(tmp_path);worker=RunCoordinator(repo,lambda _:BlockingGateway())
    request=RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='brief')
    first=worker.enqueue(request,'same')
    assert worker.enqueue(request,'same').id==first.id
    with pytest.raises(RevisionConflict):worker.enqueue(request.model_copy(update={'stage':'draft'}),'same')
    assert worker.list_events(first.id,0)[0].seq==1


def test_global_queue_has_one_active_model_request(tmp_path):
    repo,story,scene=ready(tmp_path);gateway=BlockingGateway();worker=RunCoordinator(repo,lambda _:gateway)
    worker.start()
    try:
        a=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='brief'),'a')
        assert gateway.entered.wait(2)
        b=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='brief'),'b')
        assert worker.get_run(b.id).state=='queued'
        worker.cancel(a.id)
        assert worker.get_run(a.id).state=='cancellation_requested'
        gateway.release.set()
        wait_until(lambda:worker.get_run(b.id).state=='completed')
        assert gateway.maximum==1 and gateway.calls==2
        assert worker.get_run(a.id).state=='cancelled'
    finally:gateway.release.set();worker.stop()


def test_pause_after_brief_stops_before_writer(tmp_path):
    repo,story,scene=ready(tmp_path);gateway=BlockingGateway();gateway.release.set();worker=RunCoordinator(repo,lambda _:gateway)
    worker.start()
    try:
        run=worker.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='scene',pause_after=['brief']),'pause')
        wait_until(lambda:worker.get_run(run.id).state=='paused')
        assert gateway.calls==1 and repo.get_scene(scene.id).heads.get('brief')
    finally:worker.stop()


def test_second_server_cannot_recover_first_servers_live_run(tmp_path):
    with AppInstanceLock(tmp_path):
        with pytest.raises(RuntimeError):
            with AppInstanceLock(tmp_path): pass


def test_reopen_marks_running_interrupted_without_retry(tmp_path):
    repo,story,scene=ready(tmp_path)
    first=RunCoordinator(repo,lambda _:BlockingGateway())
    run=first.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='stage',stage='brief'),'recover')
    run.state='running';first._save(run)
    gateway=BlockingGateway()
    restarted=RunCoordinator(Repository(tmp_path),lambda _:gateway)
    restarted.start()
    try:
        assert restarted.get_run(run.id).state=='interrupted'
        assert gateway.calls==0
    finally:restarted.stop()


def test_resume_reuses_completed_steps_only_if_inputs_match(tmp_path):
    repo,story,scene=ready(tmp_path);gateway=BlockingGateway();gateway.release.set()
    first=RunCoordinator(repo,lambda _:gateway);first.start()
    try:
        run=first.enqueue(RunRequest(story_id=story.id,scene_id=scene.id,mode='scene',pause_after=['brief']),'reuse')
        wait_until(lambda:first.get_run(run.id).state=='paused')
        # Simulate crash between stage commit and cursor update.
        stored=first.get_run(run.id);stored.cursor=0;first._save(stored)
        first.resume(run.id)
        wait_until(lambda:first.get_run(run.id).cursor>1)
        assert any(e.type=='reused' for e in first.list_events(run.id))
    finally:first.stop()


@pytest.mark.parametrize('state', ['completed', 'failed', 'cancelled', 'cancellation_requested'])
def test_cancel_preserves_finished_or_already_requested_run(tmp_path, state):
    repo, story, scene = ready(tmp_path)
    worker = RunCoordinator(repo)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'cancel')
    run.state = state
    run.error = 'Збережена причина'
    worker._save(run)
    worker.active_id = run.id  # Also cover the short window before worker releases ownership.
    before = worker.list_events(run.id)
    assert worker.cancel(run.id) == run
    assert worker.get_run(run.id) == run
    assert worker.list_events(run.id) == before


@pytest.mark.parametrize('state', ['queued', 'paused', 'interrupted', 'needs_review', 'alternative'])
def test_cancel_stopped_run_keeps_material_and_diagnostics(tmp_path, state):
    repo, story, scene = ready(tmp_path)
    version = repo.save_version(story.id, scene.id, 'draft', 'Авторський текст', [])
    worker = RunCoordinator(repo)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'stop')
    run.state = state
    run.error = 'Діагностика'
    worker._save(run)
    cancelled = worker.cancel(run.id)
    assert cancelled.state == 'cancelled'
    assert cancelled.cursor == run.cursor and cancelled.error == 'Діагностика'
    assert repo.read_text(version.id) == 'Авторський текст'
    count = len(worker.list_events(run.id))
    worker.cancel(run.id)
    assert len(worker.list_events(run.id)) == count


@pytest.mark.parametrize('state', ['paused', 'pause_requested', 'cancellation_requested', 'interrupted', 'needs_review', 'alternative', 'failed', 'cancelled', 'completed'])
def test_pause_does_not_change_stopped_or_pending_run(tmp_path, state):
    repo, story, scene = ready(tmp_path)
    worker = RunCoordinator(repo)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'pause-noop')
    run.state = state
    worker._save(run)
    worker.active_id = run.id
    before = worker.list_events(run.id)
    assert worker.pause(run.id) == run
    assert worker.list_events(run.id) == before


@pytest.mark.parametrize('state', ['queued', 'running', 'pause_requested'])
def test_cancel_transition_requests_cooperative_stop(tmp_path, state):
    repo, story, scene = ready(tmp_path)
    worker = RunCoordinator(repo)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'transition')
    run.state = state
    worker._save(run)
    worker.active_id = run.id if state != 'queued' else None
    assert worker.cancel(run.id).state == ('cancelled' if state == 'queued' else 'cancellation_requested')
    assert worker.cancel_event.is_set() == (state != 'queued')


@pytest.mark.parametrize('state', ['running', 'interrupted', 'failed', 'cancelled'])
def test_resume_uncertain_attempt_requires_explicit_repeat(tmp_path, state):
    from storygen.domain import StageAttempt
    repo, story, scene = ready(tmp_path)
    worker = RunCoordinator(repo)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'explicit')
    run.state = 'interrupted'
    worker._save(run)
    repo.save_attempt(StageAttempt(id='uncertain', run_id=run.id, story_id=story.id, scene_id=scene.id, stage='brief', state=state, context={'run_cursor': 0}, partial_path='partial.txt'))
    before = worker.list_events(run.id)
    with pytest.raises(ValueError, match='явне рішення'):
        worker.resume(run.id)
    assert worker.get_run(run.id) == run
    assert worker.list_events(run.id) == before
    assert worker.resume(run.id, repeat_interrupted=True).state == 'queued'


@pytest.mark.parametrize('state', ['queued', 'running', 'pause_requested', 'cancellation_requested'])
def test_recovery_interrupts_active_states_without_model_calls(tmp_path, state):
    repo, story, scene = ready(tmp_path)
    gateway = BlockingGateway()
    worker = RunCoordinator(repo, lambda _: gateway)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'startup')
    run.state = state
    worker._save(run)
    worker.recover_interrupted()
    assert worker.get_run(run.id).state == 'interrupted'
    assert gateway.calls == 0
