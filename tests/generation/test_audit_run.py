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


@pytest.mark.req('VALID-CARDS')
def test_check_after_card_invalidation_calls_the_auditor_again(tmp_path):
    from storygen.storage.link_decisions import invalidate_links
    repo, story, (scene,) = unchecked_scene(tmp_path)
    brief = link_state(repo.context_view(story.id), scene.id, 'brief')
    decide_link(repo, scene.id, 'brief', 'approve', brief.fingerprint)
    worker, run = start(repo, story, scene, Answers(DISCREPANCY), 'first')
    assert drive(worker, run.id).state == 'needs_review'
    assert link_state(repo.context_view(story.id), scene.id, 'prose').status == 'discrepancy'
    invalidate_links(repo, story.id, [scene.id], {'kind': 'character', 'ids': ['c1']})
    gateway = Answers(answer(95), answer(96))
    worker, run = start(repo, story, scene, gateway, 'second')
    run = drive(worker, run.id)
    assert run.state == 'completed', (run.state, run.error, run.checkpoint)
    assert [c.stage for c in gateway.contexts] == ['audit_brief', 'audit_prose']
    assert scene_validity(repo.context_view(story.id), scene.id) == 'valid'


@pytest.mark.req('VALID-RUN')
@pytest.mark.parametrize('case', ['incompatible', 'no_contract', 'foreign'])
def test_preview_refuses_an_invalid_prompt_of_a_called_stage(tmp_path, case):
    from tests.generation.test_audit_context import bad_prompt, force_auditor, prompt_error
    repo, story, (scene,) = unchecked_scene(tmp_path)  # brief and prose are called
    changes, stage = bad_prompt(repo, story, case)
    settings = force_auditor(repo, story, **changes)
    result = preview(repo, request(story, scene))
    assert result['ready'] is False
    assert result['reason'] == prompt_error(repo, story, settings, stage)
    with pytest.raises(ValueError, match='ромпт'):
        RunCoordinator(repo).enqueue(request(story, scene), 'bad-prompt')


def test_preview_checks_only_the_prompts_of_called_stages(tmp_path):
    from storygen.domain import PromptContract
    from tests.generation.test_audit_context import force_auditor
    repo, story, (scene,) = unchecked_scene(tmp_path)  # brief and prose are called, memory is valid
    main = repo.save_version(story.id, None, 'prompt', 'Власний промпт прози.', [],
                             prompt_contract=PromptContract(stage='audit_prose', mode='json', schema_version=1))
    wrong = repo.save_version(story.id, None, 'prompt', 'Промпт прози на місці пам’яті.', [],
                              prompt_contract=PromptContract(stage='audit_prose', mode='json', schema_version=1))
    # The main prompt is not checked as the brief prompt, and the memory link takes no call.
    force_auditor(repo, story, prompt_version_id=main.id, stage_prompt_version_ids={'audit_memory': wrong.id})
    result = preview(repo, request(story, scene))
    assert result['ready'] is True, result['reason']


@pytest.mark.req('VALID-RUN')
def test_invalid_prompt_fails_the_run_before_any_call(tmp_path):
    from tests.generation.test_audit_context import bad_prompt, force_auditor, prompt_error
    repo, story, (scene,) = unchecked_scene(tmp_path)
    gateway = Answers(answer(95))
    worker, run = start(repo, story, scene, gateway)
    changes, stage = bad_prompt(repo, story, 'no_contract')  # the prompt goes bad after the run was enqueued
    settings = force_auditor(repo, story, **changes)
    run = drive(worker, run.id)
    assert run.state == 'failed' and gateway.contexts == []
    assert run.error == prompt_error(repo, story, settings, stage)
    assert run.checkpoint['outcome'] == 'failed' and run.checkpoint['link'] == 'brief'


# R-44 PR 4: the scope `story` validates the whole book in reading order.

def book_request(story_id, fingerprint='0' * 64):
    return RunRequest(story_id=story_id, mode='audit', audit_scope='story', audit_plan_fingerprint=fingerprint)


def book_plan(repo, story):
    return RunCoordinator(repo).readiness(story.id, operation='audit_story')['operations']['audit_story']


def start_book(repo, story, gateway, request_id='book'):
    worker = RunCoordinator(repo, gateway_factory=lambda _: gateway)
    run = worker.enqueue(book_request(story.id, book_plan(repo, story)['plan_fingerprint']), request_id)
    return worker, run


def four_scenes(tmp_path):
    """s1 valid; s2 only Z2 unchecked; s3 Z1 discrepancy and Z2 unchecked; s4 without components (missing)."""
    from storygen.domain import SceneCreate
    repo, story, (s1, s2, s3) = book(tmp_path, 3)
    auditor(repo, story)
    save_manual_brief(repo, repo.get_scene(s2.id))
    decide_link(repo, s2.id, 'brief', 'approve', link_state(repo.context_view(story.id), s2.id, 'brief').fingerprint)
    save_manual_brief(repo, repo.get_scene(s3.id))
    worker, run = start(repo, story, s3, Answers(DISCREPANCY), 'scene-s3')
    assert drive(worker, run.id).state == 'needs_review'
    s4 = repo.create_scene(story.id, SceneCreate(title='Сцена 4', beats='Студія'))
    return repo, story, (s1, s2, s3, s4), run.id


def test_story_scope_request_rules():
    with pytest.raises(ValueError):
        RunRequest(story_id='s', scene_id='c', mode='audit', audit_scope='story', audit_plan_fingerprint='0' * 64)
    with pytest.raises(ValueError):
        RunRequest(story_id='s', mode='audit', audit_scope='story')
    with pytest.raises(ValueError):
        RunRequest(story_id='s', scene_id='c', mode='stage', stage='brief', audit_plan_fingerprint='0' * 64)
    assert RunRequest(story_id='s', scene_id='c', mode='audit', audit_scope='scene',
                      audit_plan_fingerprint='0' * 64).audit_plan_fingerprint == '0' * 64
    assert book_request('s').scene_id is None


def test_book_pending_in_reading_order_skips_valid_and_missing(tmp_path):
    from storygen.generation.audit_run import book_pending
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    assert book_pending(repo.context_view(story.id)) == [(s2.id, 'prose'), (s3.id, 'brief'), (s3.id, 'prose')]


def test_book_preview_counts_calls_scenes_and_fingerprints_the_plan(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    result = preview(repo, book_request(story.id))
    assert result['ready'] is True, result['reason']
    assert result['calls'] == 2  # the discrepancy takes no call
    assert result['invalid_scenes'] == 2
    assert result['links'] == [
        {'scene_id': s2.id, 'link': 'prose', 'status': 'unchecked', 'reason': None},
        {'scene_id': s3.id, 'link': 'brief', 'status': 'discrepancy', 'reason': 'Місце не збігається'},
        {'scene_id': s3.id, 'link': 'prose', 'status': 'unchecked', 'reason': None}]
    assert result['roles'] == {'auditor': {'provider': 'local', 'model': 'auditor'}}
    fingerprint = result['plan_fingerprint']
    assert len(fingerprint) == 64 and preview(repo, book_request(story.id))['plan_fingerprint'] == fingerprint
    assert book_plan(repo, story)['plan_fingerprint'] == fingerprint
    auditor(repo, story, provider=ProviderSettings(model='auditor-2'))
    assert preview(repo, book_request(story.id))['plan_fingerprint'] != fingerprint


def test_valid_book_is_not_ready(tmp_path):
    repo, story, _ = book(tmp_path, 2)
    auditor(repo, story)
    result = preview(repo, book_request(story.id))
    assert result['ready'] is False and result['reason'] == 'Книга вже валідна' and result['calls'] == 0
    with pytest.raises(ValueError, match='Книга вже валідна'):
        RunCoordinator(repo).enqueue(book_request(story.id), 'valid-book')


def test_book_run_checks_the_next_invalid_scene_and_stops_on_its_discrepancy(tmp_path):
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    gateway = Answers(answer(95))
    worker, run = start_book(repo, story, gateway)
    assert run.tasks == [{'scene_id': None, 'stage': 'audit'}]
    assert run.planned_telemetry == {'roles': {'auditor': {'provider': 'local', 'model': 'auditor'}}, 'calls': 2}
    run = drive(worker, run.id)
    assert run.state == 'needs_review', (run.state, run.error)
    assert [(c.scene_id, c.stage) for c in gateway.contexts] == [(s2.id, 'audit_prose')]
    assert run.checkpoint['scene_id'] == s3.id and run.checkpoint['phase'] == 'awaiting_author'
    assert (run.checkpoint['link'], run.checkpoint['outcome']) == ('brief', 'discrepancy')
    steps = [(e.data['scene_id'], e.data['link'], e.data['outcome']) for e in worker.list_events(run.id)
             if e.type == 'audit_step']
    assert steps == [(s2.id, 'prose', 'valid'), (s3.id, 'brief', 'discrepancy')]


def test_resume_reads_the_reading_order_again(tmp_path):
    """Review Focus 2: the author approves Z1 of s3, then edits the prose of s1; the run continues from s1."""
    from storygen.generation.dependencies import save_manual_prose
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    gateway = Answers(answer(95))
    worker, run = start_book(repo, story, gateway)
    assert drive(worker, run.id).checkpoint['scene_id'] == s3.id
    decide_link(repo, s3.id, 'brief', 'approve', link_state(repo.context_view(story.id), s3.id, 'brief').fingerprint)
    save_manual_prose(repo, s1.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(s1.id).revision)
    worker.resume(run.id)
    run = drive(worker, run.id)
    assert run.state == 'completed', (run.state, run.error, run.checkpoint)
    called = [(c.scene_id, c.stage) for c in gateway.contexts]
    assert called[1] == (s1.id, 'audit_prose')
    assert called == [(s2.id, 'audit_prose'), (s1.id, 'audit_prose'), (s1.id, 'audit_memory'), (s3.id, 'audit_prose')]
    view = repo.context_view(story.id)
    assert [scene_validity(view, s.id) for s in (s1, s2, s3)] == ['valid', 'valid', 'valid']


@pytest.mark.parametrize('stopped_state', ['needs_review', 'paused', 'failed', 'interrupted'])
def test_new_book_validation_supersedes_a_resumable_audit_of_the_story(tmp_path, stopped_state):
    repo, story, scenes, stopped = four_scenes(tmp_path)
    old = repo.get_run(stopped)
    old.state = stopped_state
    repo.save_run(old)
    worker, run = start_book(repo, story, Answers(answer(95)))
    assert repo.get_run(stopped).state == 'cancelled'
    assert [e.data for e in worker.list_events(stopped) if e.type == 'superseded'] == [{'run_id': run.id}]
    assert run.state == 'queued'


def test_book_run_with_a_changed_plan_is_refused_without_a_call(tmp_path):
    from storygen.domain import RevisionConflict
    repo, story, scenes, _ = four_scenes(tmp_path)
    fingerprint = book_plan(repo, story)['plan_fingerprint']
    auditor(repo, story, provider=ProviderSettings(model='auditor-2'))
    gateway = Answers(answer(95))
    worker = RunCoordinator(repo, gateway_factory=lambda _: gateway)
    with pytest.raises(RevisionConflict, match='План перевірки змінився. Перегляньте його ще раз'):
        worker.enqueue(book_request(story.id, fingerprint), 'stale-plan')
    assert repo.find_run_by_request_id('stale-plan') is None and gateway.contexts == []


def test_scene_run_checks_a_given_plan_fingerprint(tmp_path):
    from storygen.domain import RevisionConflict
    repo, story, (scene,) = unchecked_scene(tmp_path)
    current = preview(repo, request(story, scene))['plan_fingerprint']
    worker = RunCoordinator(repo, gateway_factory=lambda _: Answers(answer(95)))
    with pytest.raises(RevisionConflict, match='План перевірки змінився'):
        worker.enqueue(request(story, scene).model_copy(update={'audit_plan_fingerprint': '0' * 64}), 'old')
    run = worker.enqueue(request(story, scene).model_copy(update={'audit_plan_fingerprint': current}), 'fresh')
    assert run.state == 'queued'


def auditor_unavailable(repo, story, scene, link, reason):
    from tests.storage.test_link_records import store, verdict
    state = link_state(repo.context_view(story.id), scene.id, link)
    record = verdict(story.id, scene.id, link=link, fingerprint=state.fingerprint, inputs=dict(state.inputs),
                     source='auditor', outcome='unavailable', reason=reason)
    store(repo, record)
    return record.id


def test_auditor_unavailable_whose_cause_cleared_is_measured_again_and_called(tmp_path):
    from storygen.generation.audit_context import UNREADABLE
    repo, story, (scene,) = unchecked_scene(tmp_path)
    auditor_unavailable(repo, story, scene, 'prose', UNREADABLE)  # the material reads now
    assert preview(repo, request(story, scene))['calls'] == 2
    assert preview(repo, book_request(story.id))['calls'] == 2
    gateway = Answers(answer(95))
    worker, run = start_book(repo, story, gateway)
    run = drive(worker, run.id)
    assert run.state == 'completed', (run.state, run.error, run.checkpoint)
    assert [c.stage for c in gateway.contexts] == ['audit_brief', 'audit_prose']
    assert scene_validity(repo.context_view(story.id), scene.id) == 'valid'


def test_auditor_unavailable_that_still_holds_stops_without_a_call(tmp_path, monkeypatch):
    from storygen.generation import audit_context
    from storygen.generation.audit_context import FOREIGN_SOURCE
    repo, story, (scene,) = unchecked_scene(tmp_path)
    verdict_id = auditor_unavailable(repo, story, scene, 'prose', FOREIGN_SOURCE)
    inputs = audit_context._inputs

    def broken(view, story_, scene_, link, refs):
        if link == 'prose':
            raise audit_context._Unavailable(FOREIGN_SOURCE)
        return inputs(view, story_, scene_, link, refs)
    monkeypatch.setattr(audit_context, '_inputs', broken)
    assert preview(repo, request(story, scene))['calls'] == 1
    assert preview(repo, book_request(story.id))['calls'] == 1
    gateway = Answers(answer(95))
    worker, run = start(repo, story, scene, gateway, 'scene')
    run = drive(worker, run.id)
    assert run.state == 'needs_review'
    expected = {'scene_id': scene.id, 'link': 'prose', 'outcome': 'unavailable', 'verdict_id': verdict_id,
                'reason': FOREIGN_SOURCE, 'phase': 'awaiting_author'}
    assert run.checkpoint == expected
    worker, run = start_book(repo, story, gateway, 'book')
    run = drive(worker, run.id)
    assert run.state == 'needs_review' and run.checkpoint == expected
    assert [c.stage for c in gateway.contexts] == ['audit_brief']  # the scene run validated the brief; no prose call


def test_link_state_unavailable_takes_no_call_and_no_measure(tmp_path, monkeypatch):
    from storygen.generation import audit_context
    repo, story, scenes = book(tmp_path, 2)
    auditor(repo, story)
    remove_memory(repo, scenes[0])
    gateway = Answers(answer(95))
    worker, run = start_book(repo, story, gateway)
    monkeypatch.setattr(audit_context, '_inputs', lambda *a: pytest.fail('a structural unavailable is not measured'))
    assert preview(repo, book_request(story.id))['calls'] == 0
    run = drive(worker, run.id)
    assert run.state == 'needs_review' and run.checkpoint['reason'] == 'no_memory' and gateway.contexts == []


def test_overflow_verdict_is_counted(tmp_path):
    from storygen.generation.audit_context import OVERFLOW_CHARS
    repo, story, (scene,) = unchecked_scene(tmp_path)
    auditor_unavailable(repo, story, scene, 'prose', OVERFLOW_CHARS.format(chars=500000, limit=400000))
    assert preview(repo, request(story, scene))['calls'] == 2


def test_failed_book_call_needs_an_explicit_repeat(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    gateway = Answers('не JSON', answer(95))
    worker, run = start_book(repo, story, gateway)
    run = drive(worker, run.id)
    assert run.state == 'failed' and run.checkpoint['scene_id'] == scene.id
    with pytest.raises(ValueError, match='явне рішення'):
        worker.resume(run.id)
    worker.resume(run.id, repeat_interrupted=True)
    run = drive(worker, run.id)
    assert run.state == 'completed' and len(gateway.contexts) == 3


def test_coordinator_readiness_offers_the_book_audit_operation(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    operations = RunCoordinator(repo).readiness(story.id, operation='audit_story')['operations']
    assert list(operations) == ['audit_story'] and operations['audit_story']['ready'] is True
    assert operations['audit_story']['calls'] == 2 and operations['audit_story']['invalid_scenes'] == 1
    assert 'audit_story' not in RunCoordinator(repo).readiness(story.id, scene.id)['operations']


def test_book_with_one_invalid_scene_in_the_middle_calls_only_for_it(tmp_path):
    """Review Focus 1."""
    repo, story, (s1, s2, s3) = book(tmp_path, 3)
    auditor(repo, story)
    save_manual_brief(repo, repo.get_scene(s2.id))
    plan = book_plan(repo, story)
    assert plan['invalid_scenes'] == 1 and {link['scene_id'] for link in plan['links']} == {s2.id}
    gateway = Answers(answer(95))
    worker, run = start_book(repo, story, gateway)
    run = drive(worker, run.id)
    assert run.state == 'completed', (run.state, run.error, run.checkpoint)
    assert [(c.scene_id, c.stage) for c in gateway.contexts] == [(s2.id, 'audit_brief'), (s2.id, 'audit_prose')]
    view = repo.context_view(story.id)
    assert [scene_validity(view, s.id) for s in (s1, s2, s3)] == ['valid', 'valid', 'valid']


def test_book_order_follows_position_and_skips_the_trash(tmp_path):
    from storygen.generation.audit_run import book_pending
    repo, story, (s1, s2, s3) = book(tmp_path, 3)
    auditor(repo, story)
    for scene in (s1, s2, s3):
        save_manual_brief(repo, repo.get_scene(scene.id))
    repo.reorder_scenes(story.id, [s3.id, s1.id, s2.id], repo.get_story(story.id).revision)
    repo.set_scene_trashed(story.id, s2.id, repo.get_scene(s2.id).revision, False)
    scenes = list(dict.fromkeys(scene_id for scene_id, _ in book_pending(repo.context_view(story.id))))
    assert scenes == [s3.id, s1.id]


@pytest.mark.parametrize('change', ['approve', 'prose'])
def test_book_run_after_a_link_change_is_refused(tmp_path, change):
    """Review Focus 3: the author decides a link or edits prose after the preview."""
    from storygen.domain import RevisionConflict
    from storygen.generation.dependencies import save_manual_prose
    repo, story, (s1, s2, s3, s4), _ = four_scenes(tmp_path)
    fingerprint = book_plan(repo, story)['plan_fingerprint']
    if change == 'approve':
        decide_link(repo, s3.id, 'brief', 'approve', link_state(repo.context_view(story.id), s3.id, 'brief').fingerprint)
    else:
        save_manual_prose(repo, s1.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(s1.id).revision)
    gateway = Answers(answer(95))
    worker = RunCoordinator(repo, gateway_factory=lambda _: gateway)
    with pytest.raises(RevisionConflict, match='План перевірки змінився. Перегляньте його ще раз'):
        worker.enqueue(book_request(story.id, fingerprint), 'changed-link')
    assert repo.find_run_by_request_id('changed-link') is None and gateway.contexts == []


def test_cloud_book_validation_needs_a_story_budget_limit(tmp_path):
    from storygen.providers.policy import endpoint
    repo, story, (scene,) = unchecked_scene(tmp_path)
    provider = ProviderSettings(provider='openrouter', model='venice/free')
    auditor(repo, story, provider=provider)
    repo.model_policy('set_consent', role='auditor', provider='openrouter', base_url=endpoint(provider), model='venice/free')
    result = preview(repo, book_request(story.id))
    assert result['ready'] is False and result['reason'] == 'Спершу задайте явний ліміт бюджету в налаштуваннях'
