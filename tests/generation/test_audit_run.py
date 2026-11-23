"""VALID-LINKS: the run `audit` checks the links of one scene through the queue (R-44 PR 3, task 5)."""
import pytest

from storygen.authoring.blueprints import save_role_settings
from storygen.generation.audit_run import STALE_LIMIT, pending_links
from storygen.generation.readiness import pending_preview, preview
from storygen.generation.worker import RunCoordinator
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from storygen.run_models import RunRequest
from storygen.storage.link_decisions import decide_link
from storygen.storage.links import link_state, scene_links, scene_validity
from tests.generation.test_audit_context import auditor
from tests.generation.test_audit_verdict import answer, unchecked_scene
from tests.storage.test_links import book, save_manual_brief

DISCREPANCY = answer(99, [{'text': 'У завданні бібліотека, у плані студія', 'quote': None}], 'Місце не збігається')


class Answers:
    """One answer per call, in order; `during[i]` runs inside call i."""

    def __init__(self, *texts, during=None):
        self.texts, self.during, self.contexts = list(texts), during or {}, []

    def stream(self, context, cancel):
        index = len(self.contexts)
        self.contexts.append(context)
        if index in self.during:
            self.during[index]()
        yield GenerationEvent(type='delta', text=self.texts[min(index, len(self.texts) - 1)])
        yield GenerationEvent(type='terminal', finish_reason='stop')


def request(story, scene):
    return RunRequest(story_id=story.id, scene_id=scene.id, mode='audit', audit_scope='scene')


def start(repo, story, scene, gateway, request_id='audit'):
    worker = RunCoordinator(repo, gateway_factory=lambda _: gateway)
    run = worker.enqueue(request(story, scene), request_id)
    return worker, run


def drive(worker, run_id):
    run = worker.get_run(run_id)
    run.state = 'running'
    worker.repo.save_run(run)
    worker.active_id = run_id
    try:
        worker._execute(run_id)
    finally:
        worker.active_id = None
    return worker.get_run(run_id)


def remove_memory(repo, scene):
    current = repo.get_scene(scene.id)
    with repo.db.connection() as db:
        payload = current.model_copy(update={'heads': {k: v for k, v in current.heads.items() if k != 'memory'}})
        db.execute('UPDATE scenes SET payload=? WHERE id=?', (payload.model_dump_json(), current.id))


def test_request_needs_a_scene_and_scope():
    with pytest.raises(ValueError):
        RunRequest(story_id='s', mode='audit', audit_scope='scene')
    with pytest.raises(ValueError):
        RunRequest(story_id='s', scene_id='c', mode='audit')
    with pytest.raises(ValueError):
        RunRequest(story_id='s', scene_id='c', mode='scene', audit_scope='scene')


def test_pending_links_in_reading_order_skip_valid_and_missing(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    assert pending_links(repo.context_view(story.id), scene.id) == ['brief', 'prose']
    repo, story, (scene,) = book(tmp_path / 'valid')
    assert pending_links(repo.context_view(story.id), scene.id) == []


def test_preview_counts_one_call_per_pending_link(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    result = preview(repo, request(story, scene))
    assert result['ready'] is True and result['reason'] is None
    assert result['calls'] == len(pending_links(repo.context_view(story.id), scene.id)) == 2
    assert result['roles'] == {'auditor': {'provider': 'local', 'model': 'auditor'}}
    assert result['links'] == [{'link': 'brief', 'status': 'unchecked', 'reason': None},
                               {'link': 'prose', 'status': 'unchecked', 'reason': None}]


def test_preview_lists_links_that_need_no_call(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    auditor(repo, story)
    remove_memory(repo, scenes[0])
    result = preview(repo, request(story, scenes[1]))
    assert result['ready'] is True and result['calls'] == 0
    assert result['links'] == [{'link': 'brief', 'status': 'unavailable', 'reason': 'no_previous_memory'},
                               {'link': 'prose', 'status': 'unavailable', 'reason': 'no_previous_memory'}]


def test_preview_does_not_count_a_call_for_an_existing_discrepancy(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    worker, run = start(repo, story, scene, Answers(DISCREPANCY))
    drive(worker, run.id)
    result = preview(repo, request(story, scene))
    assert result['links'] == [{'link': 'brief', 'status': 'discrepancy', 'reason': 'Місце не збігається'},
                               {'link': 'prose', 'status': 'unchecked', 'reason': None}]
    assert result['calls'] == 1  # an upper bound: the later unchecked link


def test_resume_without_a_decision_stops_again_without_a_call(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    worker, run = start(repo, story, scene, Answers(DISCREPANCY))
    first = drive(worker, run.id)
    gateway = Answers(answer(95))
    worker.gateway_factory = lambda _: gateway
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert run.state == 'needs_review' and gateway.contexts == []
    assert run.checkpoint == first.checkpoint


def test_start_on_an_existing_discrepancy_stops_without_a_call(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    worker, run = start(repo, story, scene, Answers(DISCREPANCY), 'first')
    verdict_id = drive(worker, run.id).checkpoint['verdict_id']
    gateway = Answers(answer(95))
    worker, run = start(repo, story, scene, gateway, 'second')
    run = drive(worker, run.id)
    assert run.state == 'needs_review' and gateway.contexts == []
    assert run.checkpoint == {'scene_id': scene.id, 'link': 'brief', 'outcome': 'discrepancy', 'verdict_id': verdict_id,
                              'reason': 'Місце не збігається', 'phase': 'awaiting_author'}


def test_preview_uses_derived_settings_without_an_auditor_row(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_role_settings(repo, story.id, 'editor', RoleSettings(provider=ProviderSettings(model='editor-model')),
                       repo.get_story(story.id).revision)
    save_manual_brief(repo, repo.get_scene(scene.id))
    result = preview(repo, request(story, scene))
    assert result['ready'] is True
    assert result['roles'] == {'auditor': {'provider': 'local', 'model': 'editor-model'}}


def test_valid_scene_is_not_ready(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    auditor(repo, story)
    result = preview(repo, request(story, scene))
    assert result['ready'] is False and result['reason'] == 'Сцена вже валідна' and result['calls'] == 0


def test_without_editor_and_auditor_the_role_is_not_configured(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_manual_brief(repo, repo.get_scene(scene.id))
    result = preview(repo, request(story, scene))
    assert result['ready'] is False and result['reason'] == 'Роль не налаштовано: Ревізор'
    with pytest.raises(ValueError, match='Роль не налаштовано: Ревізор'):
        RunCoordinator(repo).enqueue(request(story, scene), 'no-auditor')


def test_carry_pending_link_counts_but_gets_no_call(tmp_path):
    from tests.memory.test_memory_carry import new_memory
    repo, story, scenes = book(tmp_path, 2)
    auditor(repo, story)
    new_memory(repo, scenes[0])
    view = repo.context_view(story.id)
    states = scene_links(view, scenes[1].id)
    assert (states['memory'].status, states['memory'].reason) == ('unavailable', 'carry_pending')
    links = pending_links(view, scenes[1].id)
    assert 'memory' in links
    result = preview(repo, request(story, scenes[1]))
    assert result['ready'] is True, result['reason']
    assert result['calls'] == len([link for link in links if states[link].status != 'unavailable'])


def test_two_unchecked_links_take_two_calls_and_the_scene_becomes_valid(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    gateway = Answers(answer(95), answer(96))
    worker, run = start(repo, story, scene, gateway)
    assert run.tasks == [{'scene_id': scene.id, 'stage': 'audit'}]
    assert run.planned_telemetry == {'roles': {'auditor': {'provider': 'local', 'model': 'auditor'}}, 'calls': 2}
    run = drive(worker, run.id)
    assert run.state == 'completed', run.error
    assert [c.stage for c in gateway.contexts] == ['audit_brief', 'audit_prose']
    assert scene_validity(repo.context_view(story.id), scene.id) == 'valid'
    assert run.checkpoint is None and run.error is None
    steps = [e.data for e in worker.list_events(run.id) if e.type == 'audit_step']
    assert [(s['link'], s['outcome']) for s in steps] == [('brief', 'valid'), ('prose', 'valid')]


def test_discrepancy_stops_for_review_then_approval_and_resume_check_the_next_link(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    gateway = Answers(DISCREPANCY, answer(95))
    worker, run = start(repo, story, scene, gateway)
    run = drive(worker, run.id)
    assert run.state == 'needs_review' and run.error is None
    assert len(gateway.contexts) == 1
    verdict_id = run.checkpoint['verdict_id']
    assert run.checkpoint == {'scene_id': scene.id, 'link': 'brief', 'outcome': 'discrepancy',
                              'verdict_id': verdict_id, 'reason': 'Місце не збігається', 'phase': 'awaiting_author'}
    assert verdict_id
    brief = link_state(repo.context_view(story.id), scene.id, 'brief')
    decide_link(repo, scene.id, 'brief', 'approve', brief.fingerprint)
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert run.state == 'completed', run.error
    assert [c.stage for c in gateway.contexts] == ['audit_brief', 'audit_prose']
    assert scene_validity(repo.context_view(story.id), scene.id) == 'valid'


def test_approving_the_last_link_lets_the_run_complete_on_resume(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    prose = link_state(repo.context_view(story.id), scene.id, 'prose')
    decide_link(repo, scene.id, 'prose', 'approve', prose.fingerprint)
    gateway = Answers(DISCREPANCY)
    worker, run = start(repo, story, scene, gateway)
    run = drive(worker, run.id)
    assert run.state == 'needs_review' and run.checkpoint['link'] == 'brief'
    brief = link_state(repo.context_view(story.id), scene.id, 'brief')
    decide_link(repo, scene.id, 'brief', 'approve', brief.fingerprint)
    readiness = pending_preview(repo, worker.get_run(run.id))
    assert readiness['ready'] is True and readiness['calls'] == 0
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert run.state == 'completed' and len(gateway.contexts) == 1


def test_unavailable_link_stops_for_review_without_a_call(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    auditor(repo, story)
    remove_memory(repo, scenes[0])
    gateway = Answers(answer(95))
    worker, run = start(repo, story, scenes[1], gateway)
    assert run.planned_telemetry['calls'] == 0
    run = drive(worker, run.id)
    assert run.state == 'needs_review' and run.error is None
    assert run.checkpoint == {'scene_id': scenes[1].id, 'link': 'brief', 'outcome': 'unavailable', 'verdict_id': None,
                              'reason': 'no_previous_memory', 'phase': 'awaiting_author'}
    assert gateway.contexts == []


def test_stale_verdict_rechecks_the_link(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    gateway = Answers(answer(95), during={0: lambda: save_manual_brief(repo, repo.get_scene(scene.id))})
    worker, run = start(repo, story, scene, gateway)
    run = drive(worker, run.id)
    assert run.state == 'completed', run.error
    assert [c.stage for c in gateway.contexts] == ['audit_brief', 'audit_brief', 'audit_prose']
    steps = [e.data['outcome'] for e in worker.list_events(run.id) if e.type == 'audit_step']
    assert steps == ['stale', 'valid', 'valid']


def test_three_stale_verdicts_in_a_row_fail_the_run(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    edit = lambda: save_manual_brief(repo, repo.get_scene(scene.id))
    gateway = Answers(answer(95), during={0: edit, 1: edit, 2: edit})
    worker, run = start(repo, story, scene, gateway)
    run = drive(worker, run.id)
    assert run.state == 'failed' and run.error == STALE_LIMIT
    assert STALE_LIMIT == 'Сцену змінювали під час перевірки кілька разів поспіль'
    assert len(gateway.contexts) == 3
    assert run.checkpoint['link'] == 'brief' and run.checkpoint['outcome'] == 'stale'


def test_pause_between_calls(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    holder = {}
    gateway = Answers(answer(95), answer(95), during={0: lambda: holder['worker'].pause(holder['run'])})
    worker, run = start(repo, story, scene, gateway)
    holder.update(worker=worker, run=run.id)
    run = drive(worker, run.id)
    assert run.state == 'paused' and len(gateway.contexts) == 1
    assert link_state(repo.context_view(story.id), scene.id, 'brief').status == 'valid'  # the finished call counts
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert run.state == 'completed' and len(gateway.contexts) == 2


def test_cancel_between_calls(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    holder = {}
    def request_cancel():  # the author's cancel arrives after the stream ended: the call finishes, the next does not start
        current = repo.get_run(holder['run'])
        current.state = 'cancellation_requested'
        repo.save_run(current)
    gateway = Answers(answer(95), answer(95), during={0: request_cancel})
    worker, run = start(repo, story, scene, gateway)
    holder.update(run=run.id)
    run = drive(worker, run.id)
    assert run.state == 'cancelled' and len(gateway.contexts) == 1
    assert link_state(repo.context_view(story.id), scene.id, 'brief').status == 'valid'


def test_cancelled_call_is_not_a_model_failure(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    holder = {}
    gateway = Answers(answer(95), during={0: lambda: holder['worker'].cancel_event.set()})
    worker, run = start(repo, story, scene, gateway)
    holder.update(worker=worker)
    run = drive(worker, run.id)
    assert run.state == 'cancelled' and run.error is None
    assert run.checkpoint == {'scene_id': scene.id, 'link': 'brief', 'outcome': 'cancelled', 'verdict_id': None,
                              'reason': None}
    assert link_state(repo.context_view(story.id), scene.id, 'brief').status == 'unchecked'


def test_model_failure_fails_the_run_and_needs_an_explicit_repeat(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    gateway = Answers('не JSON', answer(95))
    worker, run = start(repo, story, scene, gateway)
    run = drive(worker, run.id)
    assert run.state == 'failed' and 'Ревізор' in run.error
    assert run.checkpoint['outcome'] == 'failed' and run.checkpoint['link'] == 'brief'
    assert run.checkpoint['reason'] == run.error
    with pytest.raises(ValueError, match='явне рішення'):
        worker.resume(run.id)
    worker.resume(run.id, repeat_interrupted=True)
    run = drive(worker, run.id)
    assert run.state == 'completed' and len(gateway.contexts) == 3


def test_restart_interrupts_a_running_audit(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    worker, run = start(repo, story, scene, Answers(answer(95)))
    run.state = 'running'
    repo.save_run(run)
    RunCoordinator(repo).recover_interrupted()
    assert repo.get_run(run.id).state == 'interrupted'


def test_coordinator_readiness_offers_the_audit_operation(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    operations = RunCoordinator(repo).readiness(story.id, scene.id, operation='audit')['operations']
    assert list(operations) == ['audit'] and operations['audit']['ready'] is True and operations['audit']['calls'] == 2
    assert 'audit' not in RunCoordinator(repo).readiness(story.id, scene.id)['operations']
