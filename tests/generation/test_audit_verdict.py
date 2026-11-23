"""VALID-LINKS: one auditor call for a link of a scene and its verdict, written with CAS (R-44 PR 3, task 4)."""
import json

import pytest

from storygen.generation.audit import AuditResult, audit_link, commit_audit_verdict
from storygen.generation.audit_context import AuditUnavailable, build_audit_context
from storygen.providers.streaming import GenerationEvent
from storygen.providers.policy import ModelPolicyBlocked
from storygen.storage.link_decisions import invalidate_links
from storygen.storage.link_records import load_latest_invalidation_rowid
from storygen.storage.links import link_state, scene_validity
from tests.generation.test_audit_context import auditor
from tests.storage.test_links import book, run_for, save_manual_brief


def answer(confidence=95, discrepancies=(), summary='Узгоджено'):
    return json.dumps({'confidence': confidence, 'discrepancies': list(discrepancies), 'summary': summary}, ensure_ascii=False)


class AuditGateway:
    """Returns a configured answer, counts calls and can run a callback in the middle of the call."""

    def __init__(self, text, during=None):
        self.text, self.during, self.contexts = text, during, []

    def stream(self, context, cancel):
        self.contexts.append(context)
        if self.during:
            self.during()
        yield GenerationEvent(type='delta', text=self.text)
        yield GenerationEvent(type='terminal', finish_reason='stop')


def unchecked_scene(tmp_path, count=1):
    repo, story, scenes = book(tmp_path, count)
    auditor(repo, story)
    save_manual_brief(repo, scenes[-1])  # Z1 and Z2 of the scene become unchecked
    return repo, story, scenes


def state(repo, story, scene, link):
    return link_state(repo.context_view(story.id), scene.id, link)


def verdict_for(repo, story, scene, link):
    view = repo.context_view(story.id)
    current = link_state(view, scene.id, link)
    return view.link_verdicts.get((scene.id, link, current.fingerprint))


def test_confident_answer_without_discrepancies_is_a_valid_auditor_verdict(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    run_id = run_for(repo, story, scene, 'audit-' + scene.id)
    gateway = AuditGateway(answer(95))
    result = audit_link(repo, scene.id, 'brief', gateway, run_id=run_id)
    assert isinstance(result, AuditResult)
    assert result.outcome == 'valid' and result.verdict_id and result.attempt_id
    assert len(gateway.contexts) == 1 and gateway.contexts[0].stage == 'audit_brief'
    current = state(repo, story, scene, 'brief')
    assert (current.status, current.source) == ('valid', 'auditor')
    verdict = verdict_for(repo, story, scene, 'brief')
    assert verdict.id == result.verdict_id and verdict.source == 'auditor' and verdict.outcome == 'valid'
    assert verdict.confidence == 95 and verdict.discrepancies == [] and verdict.reason == 'Узгоджено'
    assert verdict.attempt_id == result.attempt_id and verdict.run_id == run_id
    assert verdict.inputs == current.inputs and verdict.fingerprint == current.fingerprint
    attempt = repo.get_attempt(result.attempt_id)
    assert attempt.state == 'completed' and attempt.stage == 'audit_brief' and attempt.result_version_id is None
    assert attempt.context['audit_verdict'] == {'confidence': 95, 'discrepancies': [], 'summary': 'Узгоджено',
                                                'outcome': 'valid'}


def test_audit_saves_no_version(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    before = repo.get_scene(scene.id)
    audit_link(repo, scene.id, 'prose', AuditGateway(answer(95)))
    after = repo.get_scene(scene.id)
    assert after.heads == before.heads and after.revision == before.revision


def test_one_discrepancy_with_high_confidence_is_a_discrepancy(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    found = [{'text': 'У завданні бібліотека, у прозі студія', 'quote': 'Олена увійшла до студії'}]
    result = audit_link(repo, scene.id, 'prose', AuditGateway(answer(99, found, 'Місце не збігається')))
    assert result.outcome == 'discrepancy' and result.verdict_id
    current = state(repo, story, scene, 'prose')
    assert (current.status, current.source) == ('discrepancy', 'auditor')
    verdict = verdict_for(repo, story, scene, 'prose')
    assert verdict.confidence == 99 and verdict.reason == 'Місце не збігається'
    assert [d.model_dump() for d in verdict.discrepancies] == found
    assert scene_validity(repo.context_view(story.id), scene.id) == 'discrepancy'  # badge «Розбіжність»


@pytest.mark.parametrize('raw', ['не JSON', answer(95, [{'text': '', 'quote': None}])])
def test_wrong_answer_fails_the_attempt_without_verdict_or_retry(tmp_path, raw):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    gateway = AuditGateway(raw)
    result = audit_link(repo, scene.id, 'brief', gateway)
    assert result.outcome == 'failed' and result.verdict_id is None and result.attempt_id
    assert len(gateway.contexts) == 1
    attempt = repo.get_attempt(result.attempt_id)
    assert attempt.state == 'failed' and 'Ревізор' in attempt.error and 'audit_verdict' not in attempt.context
    assert attempt.context['audit_failure']['category'] == 'protocol'
    assert result.reason == attempt.error
    assert verdict_for(repo, story, scene, 'brief') is None
    assert state(repo, story, scene, 'brief').status == 'unchecked'


def test_overflow_writes_an_unavailable_verdict_without_a_call(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    auditor(repo, story, max_input_chars=100)
    gateway = AuditGateway(answer(95))
    result = audit_link(repo, scene.id, 'prose', gateway)
    assert len(gateway.contexts) == 0
    assert result.outcome == 'unavailable' and result.verdict_id and result.attempt_id is None
    assert 'перевищує ліміт Ревізора' in result.reason
    verdict = verdict_for(repo, story, scene, 'prose')
    assert verdict.id == result.verdict_id and verdict.source == 'auditor' and verdict.outcome == 'unavailable'
    assert verdict.reason == result.reason and verdict.confidence is None and verdict.attempt_id is None
    current = state(repo, story, scene, 'prose')
    assert (current.status, current.source, current.reason) == ('unavailable', 'auditor', result.reason)


def test_unavailable_link_state_gives_no_call_and_no_verdict(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    auditor(repo, story)
    first = repo.get_scene(scenes[0].id)
    with repo.db.connection() as db:
        payload = first.model_copy(update={'heads': {k: v for k, v in first.heads.items() if k != 'memory'}})
        db.execute('UPDATE scenes SET payload=? WHERE id=?', (payload.model_dump_json(), first.id))
    gateway = AuditGateway(answer(95))
    result = audit_link(repo, scenes[1].id, 'brief', gateway)
    assert len(gateway.contexts) == 0
    assert result == AuditResult('unavailable', None, None, 'no_previous_memory')
    assert verdict_for(repo, story, scenes[1], 'brief') is None


def test_author_brief_edit_during_the_call_makes_the_verdict_stale(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    gateway = AuditGateway(answer(95), during=lambda: save_manual_brief(repo, repo.get_scene(scene.id)))
    result = audit_link(repo, scene.id, 'brief', gateway)
    assert result.outcome == 'stale' and result.verdict_id is None and result.attempt_id
    attempt = repo.get_attempt(result.attempt_id)
    assert attempt.state == 'completed' and attempt.context['audit_verdict']['outcome'] == 'valid'
    assert state(repo, story, scene, 'brief').status == 'unchecked'
    view = repo.context_view(story.id)
    assert not [v for v in view.link_verdicts.values() if v.source == 'auditor']


def test_invalidation_of_the_scene_during_the_call_makes_the_verdict_stale(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    cause = {'kind': 'character', 'ids': ['olena']}
    gateway = AuditGateway(answer(95), during=lambda: invalidate_links(repo, story.id, [scene.id], cause))
    result = audit_link(repo, scene.id, 'prose', gateway)
    assert result.outcome == 'stale' and result.verdict_id is None
    assert repo.get_attempt(result.attempt_id).context['audit_verdict']['outcome'] == 'valid'
    assert state(repo, story, scene, 'prose').status == 'unchecked'


def test_invalidation_of_another_scene_during_the_call_keeps_the_verdict(tmp_path):
    repo, story, scenes = unchecked_scene(tmp_path, 2)
    cause = {'kind': 'location', 'ids': ['studio']}
    gateway = AuditGateway(answer(95), during=lambda: invalidate_links(repo, story.id, [scenes[0].id], cause))
    result = audit_link(repo, scenes[1].id, 'prose', gateway)
    assert result.outcome == 'valid' and result.verdict_id
    current = state(repo, story, scenes[1], 'prose')
    assert (current.status, current.source) == ('valid', 'auditor')


def test_invalidation_before_the_call_is_behind_the_marker(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    invalidate_links(repo, story.id, [scene.id], {'kind': 'character', 'ids': ['olena']})
    with repo.db.connection() as db:
        latest = load_latest_invalidation_rowid(db, story.id)
    assert latest > 0
    context = build_audit_context(repo, scene.id, 'prose')
    assert context.fragments['invalidation_marker'] == str(latest)
    result = audit_link(repo, scene.id, 'prose', AuditGateway(answer(95)))
    assert result.outcome == 'valid'
    assert state(repo, story, scene, 'prose').status == 'valid'  # a later valid verdict clears the invalidation


def test_latest_invalidation_rowid_is_zero_without_records(tmp_path):
    repo, story, _ = book(tmp_path)
    with repo.db.connection() as db:
        assert load_latest_invalidation_rowid(db, story.id) == 0


def test_commit_is_a_no_op_for_an_attempt_without_a_verdict(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    result = audit_link(repo, scene.id, 'brief', AuditGateway('не JSON'))
    assert commit_audit_verdict(repo, repo.get_attempt(result.attempt_id)) is None


def test_refusal_mark_of_the_auditor_blocks_the_call(tmp_path):
    from storygen.providers.policy import REFUSAL_BLOCKED, endpoint
    from storygen.web.localization import translate
    repo, story, (scene,) = unchecked_scene(tmp_path)
    settings = build_audit_context(repo, scene.id, 'brief').settings.provider
    entry = {'rating': [0, 0, 0], 'at': '2026-11-23T00:00:00+00:00', 'story_id': story.id, 'scene_id': scene.id,
             'attempt_id': 'a', 'category': 'refusal_content'}
    repo.model_policy('add_refusal', entry=entry, role='auditor', provider=settings.provider,
                      base_url=endpoint(settings), model=settings.model)
    gateway = AuditGateway(answer(95))
    with pytest.raises(ModelPolicyBlocked) as blocked:
        audit_link(repo, scene.id, 'brief', gateway)
    assert blocked.value.kind == 'refusal'
    assert str(blocked.value) == translate('policy.block.refusal.auditor', 'uk', p0=settings.model, p1='0/0/0', p2='0/0/0')
    assert str(blocked.value) == REFUSAL_BLOCKED.format(model=settings.model, role='Ревізор', seen='0/0/0', rating='0/0/0')
    assert len(gateway.contexts) == 0
    assert verdict_for(repo, story, scene, 'brief') is None


def test_low_confidence_without_discrepancies_is_a_discrepancy(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    result = audit_link(repo, scene.id, 'brief', AuditGateway(answer(89)))
    assert result.outcome == 'discrepancy' and result.verdict_id
    verdict = verdict_for(repo, story, scene, 'brief')
    assert verdict.outcome == 'discrepancy' and verdict.confidence == 89 and verdict.discrepancies == []


def test_overflow_verdict_is_measured_again_after_the_limit_grows(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    auditor(repo, story, max_input_chars=100)
    assert audit_link(repo, scene.id, 'prose', AuditGateway(answer(95))).outcome == 'unavailable'
    auditor(repo, story)
    gateway = AuditGateway(answer(95))
    result = audit_link(repo, scene.id, 'prose', gateway)
    assert len(gateway.contexts) == 1 and result.outcome == 'valid'
    assert (state(repo, story, scene, 'prose').status, state(repo, story, scene, 'prose').source) == ('valid', 'auditor')


def test_card_invalidation_during_a_memory_audit_keeps_the_memory_verdict(tmp_path):
    """Design §7: only an invalidation of this link makes the verdict stale; a card change covers Z1 and Z2 only."""
    from storygen.generation.dependencies import save_manual_prose
    repo, story, (scene,) = book(tmp_path)
    auditor(repo, story)
    save_manual_prose(repo, scene.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(scene.id).revision)
    cause = {'kind': 'character', 'ids': ['olena']}
    gateway = AuditGateway(answer(95), during=lambda: invalidate_links(repo, story.id, [scene.id], cause))
    result = audit_link(repo, scene.id, 'memory', gateway)
    assert result.outcome == 'valid' and result.verdict_id
    assert 'memory' not in repo.context_view(story.id).link_invalidations[-1].links
    current = state(repo, story, scene, 'memory')
    assert (current.status, current.source) == ('valid', 'auditor')


def test_valid_memory_verdict_records_the_prose_equivalence(tmp_path):
    from storygen.generation.dependencies import save_manual_prose
    repo, story, (scene,) = book(tmp_path)
    auditor(repo, story)
    old = repo.get_scene(scene.id).heads['prose']
    save_manual_prose(repo, scene.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(scene.id).revision)
    new = repo.get_scene(scene.id).heads['prose']
    gateway = AuditGateway(answer(95))
    result = audit_link(repo, scene.id, 'memory', gateway)
    assert result.outcome == 'valid' and gateway.contexts[0].stage == 'audit_memory'
    assert (state(repo, story, scene, 'memory').status, state(repo, story, scene, 'memory').source) == ('valid', 'auditor')
    records = repo.context_view(story.id).prose_equivalences
    assert [(r.scene_id, r.old_prose_id, r.new_prose_id, r.verdict_id) for r in records] == [(scene.id, old, new, result.verdict_id)]
