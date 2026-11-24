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


def test_a_failing_progress_computation_does_not_fail_the_run(tmp_path, monkeypatch):
    import storygen.generation.run_progress as module
    monkeypatch.setattr(module, 'run_progress', lambda *_: (_ for _ in ()).throw(RuntimeError('boom')))
    repo, story, scene = ready(tmp_path)
    gateway = BlockingGateway(); gateway.release.set()
    worker = RunCoordinator(repo, lambda _: gateway)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'brief')
    run = drive(worker, run.id)
    events = worker.list_events(run.id)
    assert run.state == 'completed' and any(e.type == 'stage_finished' for e in events)
    assert not any(e.type == 'progress' for e in events) and events[-1].type == 'state'


def test_list_run_events_filters_by_type(tmp_path):
    repo, worker, run, _ = _setup(tmp_path)
    worker.event(run.id, 'note', {})
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a1', 'usage': {}})
    kinds = lambda **kw: {e.type for e in repo.list_run_events(run.id, **kw)}
    assert kinds(types=('stage_finished',)) == {'stage_finished'}
    assert kinds(types=()) == kinds() and 'note' in kinds()


def test_spent_rounds_half_up_at_the_boundary(tmp_path):
    repo, worker, run, _ = _setup(tmp_path)
    for key in ('a1', 'a2'):
        worker.event(run.id, 'stage_finished', {'attempt_id': key, 'usage': {'cost': 0.000025}})
    assert run_progress(repo, repo.get_run(run.id))['spent_usd'] == '0.0001'


def test_single_scene_audit_progress_is_one_of_one(tmp_path):
    from tests.generation.test_audit_run import request as audit_request
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    run = Run(id='r', story_id=story.id, request_id='q', tasks=[], request=audit_request(story, s3))
    progress = progress_from_events(run, [])
    assert progress['scene'] == {'id': s3.id, 'index': 1, 'total': 1}


def test_extend_plan_rules():
    from storygen.generation.run_progress import extend_plan
    plan = {'roles': {}, 'calls': 4, 'cost_bound_usd': '2.1000', 'scenes': 16}
    done = {'calls': {'done': 5, 'planned': 4}, 'spent_usd': '0.0200', 'spent_known': True}
    resume = {'calls': 3, 'cost': {'total_usd': '0.3000'},
              'links': [{'scene_id': 's5'}, {'scene_id': 's6'}, {'scene_id': 's6'}]}
    visited = ['s1', 's2', 's3', 's4', 's5']
    assert extend_plan(plan, done, resume, visited) == {'roles': {}, 'calls': 8, 'cost_bound_usd': '0.3200', 'scenes': 6}
    assert extend_plan(plan, {**done, 'spent_known': False}, resume, visited)['cost_bound_usd'] is None
    assert extend_plan(plan, done, {**resume, 'cost': {'total_usd': None}}, visited)['cost_bound_usd'] is None
    assert extend_plan(plan, done, {**resume, 'calls': 0}, visited) == plan
    assert extend_plan(None, done, resume, visited) is None
    assert extend_plan({'roles': {}, 'calls': 3}, {**done, 'calls': {'done': 1, 'planned': 3}}, {'calls': 2}, []) == {'roles': {}, 'calls': 3}
    assert extend_plan(plan, done, {**resume, 'cost': {'total_usd': '0.00001'}}, visited)['cost_bound_usd'] == '0.0201'  # ceiling


def test_enqueue_stores_the_cost_bound_and_scenes_of_the_preview(tmp_path, monkeypatch):
    repo, story, _, _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    assert run.planned_telemetry == {'roles': {'auditor': {'provider': 'local', 'model': 'auditor'}}, 'calls': 2,
                                     'cost_bound_usd': None, 'scenes': 2}
    monkeypatch.setattr('storygen.generation.audit_cost.upper_bound',
                        lambda repo, settings, calls: {'per_call_usd': '0.0309', 'total_usd': '0.0618', 'reason': None})
    repo2, story2, _, _ = four_scenes(tmp_path / 'priced')
    _, priced = start_book(repo2, story2, Answers(answer(95)))
    assert priced.planned_telemetry['cost_bound_usd'] == '0.0618'


def test_resume_extends_the_plan_without_counting_a_visited_scene_twice(tmp_path):
    from storygen.storage.links import link_state
    from tests.generation.test_audit_run import decide_link
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    assert drive(worker, run.id).checkpoint['scene_id'] == s3.id  # one call (s2 prose), stop on s3 brief
    decide_link(repo, s3.id, 'brief', 'approve', link_state(repo.context_view(story.id), s3.id, 'brief').fingerprint)
    resumed = worker.resume(run.id)
    assert resumed.planned_telemetry == {'roles': {'auditor': {'provider': 'local', 'model': 'auditor'}}, 'calls': 2,
                                         'cost_bound_usd': None, 'scenes': 2}
    assert repo.get_run(run.id).planned_telemetry == resumed.planned_telemetry


def test_finishing_resume_keeps_the_plan(tmp_path):
    from storygen.storage.links import link_state
    from tests.generation.test_audit_run import decide_link
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    drive(worker, run.id)
    status = lambda link: link_state(repo.context_view(story.id), s3.id, link).status
    assert [status(link) for link in ('brief', 'prose', 'memory')] == ['discrepancy', 'unchecked', 'valid']
    for link in ('brief', 'prose'):  # the author decides the two pending links; memory is already valid
        decide_link(repo, s3.id, link, 'approve', link_state(repo.context_view(story.id), s3.id, link).fingerprint)
    before = repo.get_run(run.id).planned_telemetry
    assert worker.run_readiness(run.id)['calls'] == 0  # the resume preview has nothing left to call
    worker.resume(run.id)
    assert repo.get_run(run.id).planned_telemetry == before
    assert drive(worker, run.id).state == 'completed'


def test_a_failed_call_costs_nothing_but_a_cancelled_one_is_unknown(tmp_path):
    """A failed attempt without a price was not billed ($0). A cancelled non-streamed call is billed late by the provider
    (`_settle_late` writes it to billing only), so a cancelled attempt without a price is unknown, not $0."""
    from storygen.generation.run_progress import extend_plan
    repo, worker, run, _ = _setup(tmp_path)
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a1', 'state': 'failed', 'usage': {}})
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a2', 'state': 'completed', 'usage': {'cost': 0.01}})
    progress = run_progress(repo, repo.get_run(run.id))
    assert progress['calls']['done'] == 2
    assert (progress['spent_usd'], progress['spent_known']) == ('0.0100', True)
    plan = {'roles': {}, 'calls': 2, 'cost_bound_usd': '0.0618'}
    assert extend_plan(plan, progress, {'calls': 1, 'cost': {'total_usd': '0.0309'}}, [])['cost_bound_usd'] == '0.0409'
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a3', 'state': 'cancelled', 'usage': {}})
    progress = run_progress(repo, repo.get_run(run.id))
    assert progress['calls']['done'] == 3
    assert (progress['spent_usd'], progress['spent_known']) == ('0.0100', False)
    assert extend_plan(plan, progress, {'calls': 1, 'cost': {'total_usd': '0.0309'}}, [])['cost_bound_usd'] is None
    # a cancelled attempt that carries a price adds it; a completed attempt or a legacy event without a price is unknown
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a4', 'state': 'cancelled', 'usage': {'cost': 0.002}})
    assert run_progress(repo, repo.get_run(run.id))['spent_usd'] == '0.0120'
    worker.event(run.id, 'stage_finished', {'attempt_id': 'a5', 'usage': {}})
    assert run_progress(repo, repo.get_run(run.id))['spent_known'] is False


def test_audit_scene_after_a_revisit_is_the_latest_event_scene(tmp_path):
    repo, worker, run, (s1, s2, s3, s4) = _setup(tmp_path)
    worker.event(run.id, 'stage_started', {'stage': 'audit_prose', 'scene_id': s1.id, 'link': 'prose'})
    worker.event(run.id, 'audit_step', {'scene_id': s2.id, 'link': 'brief'})
    worker.event(run.id, 'audit_step', {'scene_id': s1.id, 'link': 'memory'})
    progress = run_progress(repo, repo.get_run(run.id))
    assert progress['scene'] == {'id': s1.id, 'index': 2, 'total': 2} and progress['step'] == {'link': 'memory'}


class _Priced:
    """Answers with a price: every completed call costs $0.01."""

    def __init__(self, inner):
        self.inner = inner

    def stream(self, context, cancel):
        from storygen.providers.streaming import GenerationEvent
        for event in self.inner.stream(context, cancel):
            yield event.model_copy(update={'usage': {'cost': 0.01}}) if event.type == 'terminal' else event


def test_priced_resume_extends_the_bound_after_a_failed_call(tmp_path, monkeypatch):
    """VALID-RUN-S11 end to end: resume adds the resume preview's bound to the accumulated spend; a failed call before it
    (empty usage) does not blank the bound."""
    from storygen.storage.links import link_state
    from tests.generation.test_audit_run import decide_link
    monkeypatch.setattr('storygen.generation.audit_cost.upper_bound',
                        lambda repo, settings, calls: {'per_call_usd': '0.0309', 'total_usd': f'{0.0309 * calls:.4f}', 'reason': None})
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, _Priced(Answers(answer(95))))
    assert run.planned_telemetry['cost_bound_usd'] == '0.0618'
    assert drive(worker, run.id).checkpoint['scene_id'] == s3.id  # one priced call (s2 prose), stop on s3 brief
    worker.event(run.id, 'stage_finished', {'attempt_id': 'failed-1', 'state': 'failed', 'usage': {}})
    assert run_progress(repo, repo.get_run(run.id))['spent_usd'] == '0.0100'
    decide_link(repo, s3.id, 'brief', 'approve', link_state(repo.context_view(story.id), s3.id, 'brief').fingerprint)
    readiness = worker.run_readiness(run.id)
    resumed = worker.resume(run.id)
    assert readiness['calls'] == 1 and readiness['cost']['total_usd'] == '0.0309'  # s3 prose is the one remaining call
    assert resumed.planned_telemetry['cost_bound_usd'] == '0.0409'  # 0.0100 spent + 0.0309
    assert resumed.planned_telemetry['calls'] == 3  # 2 done-or-planned before + 1 remaining
    assert repo.get_run(run.id).planned_telemetry == resumed.planned_telemetry


def test_resume_survives_a_failing_progress_and_keeps_the_plan(tmp_path, monkeypatch):
    import storygen.generation.run_progress as module
    from storygen.storage.links import link_state
    from tests.generation.test_audit_run import decide_link
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    drive(worker, run.id)
    decide_link(repo, s3.id, 'brief', 'approve', link_state(repo.context_view(story.id), s3.id, 'brief').fingerprint)
    before = repo.get_run(run.id).planned_telemetry
    monkeypatch.setattr(module, 'progress_from_events', lambda *_: (_ for _ in ()).throw(RuntimeError('boom')))
    resumed = worker.resume(run.id)
    assert resumed.state == 'queued' and repo.get_run(run.id).planned_telemetry == before


def test_resume_reads_only_the_progress_events(tmp_path, monkeypatch):
    from storygen.generation.run_progress import PROGRESS_EVENTS
    from storygen.storage.links import link_state
    from tests.generation.test_audit_run import decide_link
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    worker, run = start_book(repo, story, Answers(answer(95)))
    drive(worker, run.id)
    decide_link(repo, s3.id, 'brief', 'approve', link_state(repo.context_view(story.id), s3.id, 'brief').fingerprint)
    seen = []
    original = repo.list_run_events
    monkeypatch.setattr(repo, 'list_run_events', lambda run_id, after_seq=0, types=None: seen.append(types) or original(run_id, after_seq, types))
    worker.resume(run.id)
    assert seen and all(types == PROGRESS_EVENTS for types in seen)
