"""PROGRESS-UX §2: the server computes run progress from events and the saved run, and emits the `progress` event."""
from storygen.generation.run_progress import progress_from_events, run_progress
from storygen.generation.worker import RunCoordinator
from storygen.run_models import Run, RunRequest
from tests.generation.test_audit_run import Answers, answer, drive, four_scenes, start_book
from tests.generation.test_editor_loop import seeded
from tests.generation.test_worker import BlockingGateway, ready


def _setup(tmp_path):
    repo, story, scenes, _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    run.planned_telemetry = {**run.planned_telemetry, 'scenes': 2, 'cost_bound_usd': '0.0618'}
    repo.save_run(run)
    return repo, worker, run, scenes


def test_progress_counts_calls_and_spent_once_per_attempt(tmp_path):
    repo, worker, run, (s1, s2, s3, s4) = _setup(tmp_path)
    worker.event(run.id, 'stage_started', {'stage': 'audit_prose', 'scene_id': s2.id, 'link': 'prose'})
    for _ in range(2):  # a replayed event counts once
        worker.event(run.id, 'stage_finished', {'attempt_id': 'a1', 'state': 'completed', 'usage': {'cost': 0.012}})
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a2', 'state': 'completed', 'usage': {'cost': {'usd': 0.0031}}})
    progress = run_progress(repo, repo.get_run(run.id))
    assert progress['calls'] == {'done': 2, 'planned': 2}
    assert (progress['spent_usd'], progress['spent_known'], progress['bound_usd']) == ('0.0151', True, '0.0618')
    assert progress['scene'] == {'id': s2.id, 'index': 1, 'total': 2} and progress['step'] == {'link': 'prose'}


def test_a_call_without_a_price_makes_spent_unknown(tmp_path):
    repo, worker, run, _ = _setup(tmp_path)
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a1', 'state': 'completed', 'usage': {'cost': 0.01}})
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a2', 'state': 'completed', 'usage': {}})
    progress = run_progress(repo, repo.get_run(run.id))
    assert progress['spent_known'] is False and progress['spent_usd'] == '0.0100'


def test_progress_without_events_is_zero(tmp_path):
    repo, worker, run, _ = _setup(tmp_path)
    progress = run_progress(repo, repo.get_run(run.id))
    assert progress['calls'] == {'done': 0, 'planned': 2}
    assert (progress['spent_usd'], progress['spent_known']) == ('0.0000', True)
    assert progress['scene']['index'] == 0 and progress['step'] is None and progress['stopped'] is None


def test_book_stop_emits_progress_after_each_step_and_names_the_stop(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    run = drive(worker, run.id)
    types = [e.type for e in worker.list_events(run.id)
             if e.type in {'stage_started', 'audit_step', 'stage_finished', 'progress'}]
    assert types == ['stage_started', 'progress', 'audit_step', 'progress', 'stage_finished', 'progress',
                     'audit_step', 'progress']
    progress = run_progress(repo, run)  # Р6: the stop is read from the saved run, not from the event
    assert progress['stopped'] == {'scene_id': s3.id, 'link': 'brief', 'outcome': 'discrepancy'}
    assert progress['scene']['id'] == s3.id and progress['scene']['index'] == 2 and progress['calls']['done'] == 1


def test_progress_after_stage_started_names_the_current_link(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    drive(worker, run.id)
    events = worker.list_events(run.id)
    started = next(i for i, e in enumerate(events) if e.type == 'stage_started')
    during = events[started + 1]
    assert during.type == 'progress'
    assert during.data['step'] == {'link': 'prose'} and during.data['scene']['id'] == s2.id
    assert during.data['calls']['done'] == 0


def test_generation_progress_names_the_scene_and_stage_of_the_cursor():
    tasks = [{'scene_id': 'a', 'stage': 'brief'}, {'scene_id': 'a', 'stage': 'draft'},
             {'scene_id': 'b', 'stage': 'brief'}, {'scene_id': 'b', 'stage': 'draft'}]
    run = Run(id='r', story_id='s', request_id='q', tasks=tasks, cursor=2,
              request=RunRequest(story_id='s', scene_id='a', mode='remaining'), planned_telemetry={'roles': {}, 'calls': 4})
    progress = progress_from_events(run, [])
    assert progress['scene'] == {'id': 'b', 'index': 2, 'total': 2} and progress['step'] == {'stage': 'brief'}
    assert progress_from_events(run.model_copy(update={'cursor': 4}), [])['step'] == {'stage': 'draft'}  # completed: last task
    prepare = run.model_copy(update={'tasks': [{'scene_id': None, 'stage': 'prepare'}], 'cursor': 0})
    assert progress_from_events(prepare, [])['scene'] is None
    assert progress_from_events(prepare, [])['bound_usd'] is None


def test_memory_carry_has_no_progress():
    run = Run(id='r', story_id='s', request_id='q', tasks=[],
              request=RunRequest(story_id='s', scene_id='a', mode='memory_carry'))
    assert progress_from_events(run, []) is None


def test_stage_run_emits_progress_after_the_cursor_moves(tmp_path):
    repo, story, scene = ready(tmp_path)
    gateway = BlockingGateway(); gateway.release.set()
    worker = RunCoordinator(repo, lambda _: gateway)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'brief')
    drive(worker, run.id)
    events = worker.list_events(run.id)
    finished = next(i for i, e in enumerate(events) if e.type == 'stage_finished')
    progress = events[finished + 1]
    assert progress.type == 'progress' and progress.data['calls'] == {'done': 1, 'planned': 1}
    assert events[-1].type == 'state'  # the closing state event stays last


def test_editor_loop_pass_emits_progress(tmp_path):
    repo, scene, draft, worker, run, calls = seeded(tmp_path, ['{"edits":[]}'])
    worker._execute(run.id)
    events = worker.list_events(run.id)
    steps = sum(e.type in {'stage_started', 'stage_finished'} for e in events)
    assert sum(e.type == 'progress' for e in events) == steps >= 2
