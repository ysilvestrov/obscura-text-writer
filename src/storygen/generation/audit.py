"""VALID-LINKS: one auditor call for a link of a scene and its verdict (R-44 PR 3).

The call goes through execute_stage (policy, budget, attempt); the result is not a version but a LinkVerdict written in
one BEGIN IMMEDIATE transaction with two checks: the link fingerprint is the one the context was built for, and no
LinkInvalidation of this link of the scene appeared after the context's invalidation marker. Otherwise the verdict stays only in
the attempt (`stale`): the auditor may have read an old card or an old component."""
import threading
from dataclasses import dataclass
from typing import Literal

from ..storage.link_decisions import write_auditor_verdict
from .audit_context import AuditUnavailable, build_audit_context
from .audit_output import AuditResponse, outcome, verdict_discrepancies

STALE = 'Зв’язок сцени змінився під час перевірки; висновок не застосовано'


@dataclass(frozen=True)
class AuditResult:
    outcome: Literal['valid', 'discrepancy', 'unavailable', 'failed', 'stale']
    verdict_id: str | None
    attempt_id: str | None
    reason: str | None


def _write_unavailable(repo, story_id, scene_id, link, unavailable: AuditUnavailable, run_id) -> AuditResult:
    """Overflow or a structural problem of the material: a verdict for the fingerprint seen at build time. A link that
    link_state itself reports as unavailable gets no record (write_auditor_verdict: 'structural')."""
    status, verdict_id = write_auditor_verdict(repo, story_id, scene_id, link, fingerprint=unavailable.fingerprint,
                                               marker=None, outcome='unavailable', reason=unavailable.reason[:2000],
                                               run_id=run_id)
    if status == 'stale':
        return AuditResult('stale', None, None, STALE)
    return AuditResult('unavailable', verdict_id, None, unavailable.reason)


def commit_audit_verdict(repo, attempt) -> str | None:
    """The verdict of a completed audit attempt, or None when the link fingerprint or an invalidation of this link
    appeared since the context was built (the verdict then stays only in `attempt.context['audit_verdict']`)."""
    payload = attempt.context.get('audit_verdict')
    if attempt.state != 'completed' or payload is None:
        return None
    fragments = attempt.context['fragments']
    response = AuditResponse.model_validate({key: payload[key] for key in ('confidence', 'discrepancies', 'summary')})
    status, verdict_id = write_auditor_verdict(
        repo, attempt.story_id, attempt.scene_id, fragments['audit_link'], fingerprint=fragments['audit_fingerprint'],
        marker=int(fragments['invalidation_marker']), outcome=outcome(response), confidence=response.confidence,
        discrepancies=verdict_discrepancies(response), reason=response.summary or None, attempt_id=attempt.id,
        run_id=attempt.run_id)
    return verdict_id if status == 'written' else None


def audit_link(repo, scene_id: str, link: str, gateway, *, run_id: str | None = None, task_cursor: int | None = None,
               cancel: threading.Event | None = None) -> AuditResult:
    """Model policy blocks (ModelPolicyBlocked), budget refusals and stream exceptions propagate as for other stages;
    a cancelled or failed attempt gives `failed` with the attempt's error and no automatic retry."""
    from .stages import execute_stage
    story_id = repo.get_scene(scene_id).story_id
    context = build_audit_context(repo, scene_id, link)
    if isinstance(context, AuditUnavailable):
        return _write_unavailable(repo, story_id, scene_id, link, context, run_id)
    attempt = execute_stage(repo, scene_id, context.stage, context, gateway, cancel or threading.Event(), lambda *_: None,
                            run_id, task_cursor)
    if attempt.state != 'completed':
        return AuditResult('failed', None, attempt.id, attempt.error)
    verdict_id = commit_audit_verdict(repo, attempt)
    if verdict_id is None:
        return AuditResult('stale', None, attempt.id, STALE)
    return AuditResult(attempt.context['audit_verdict']['outcome'], verdict_id, attempt.id,
                       attempt.context['audit_verdict']['summary'] or None)
