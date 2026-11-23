"""VALID-LINKS: the queue run `audit` for one scene (R-44 PR 3, design §9).

On every step the worker reads the scene again and checks its first link that still needs a check, in reading order:
the author's decisions and edits change the set between calls. `valid` goes on; `discrepancy` and `unavailable` stop in
`needs_review` with a checkpoint (phase `awaiting_author`); a link already in `discrepancy` (an auditor verdict for its
current fingerprint) stops there with that verdict and no new call, on start and on resume; a stale verdict reads the link again (at most STALE_STEPS times in a row). Pause and
cancel act between calls. It is a model run: a restart leaves it `interrupted`, and a failed call is repeated only on the
author's explicit decision (RunCoordinator.resume)."""
from pydantic import ValidationError

from ..storage.links import scene_links, scene_validity

PENDING = ('unchecked', 'discrepancy', 'unavailable')
STALE_STEPS = 3
ALREADY_VALID = 'Сцена вже валідна'
STALE_LIMIT = 'Сцену змінювали під час перевірки кілька разів поспіль'


def pending_links(view, scene_id: str) -> list[str]:
    """The links still to check, in reading order brief → prose → memory; `valid` and `missing` are left out."""
    return [link for link, state in scene_links(view, scene_id).items() if state.status in PENDING]


def _called(state) -> bool:
    """An `unchecked` link is called; an auditor's overflow verdict is measured again first and may be called. A
    `discrepancy` keeps its verdict until the author decides, and link_state's own `unavailable` gets no call."""
    return state.status == 'unchecked' or (state.status == 'unavailable' and state.source is not None)


def _calls(states, links) -> int:
    """An upper bound: an earlier discrepancy or unavailable link stops the run before the later links are called."""
    return sum(1 for link in links if _called(states[link]))


def readiness(repo, request, view=None, resume=False) -> dict:
    """Read-only preflight of an audit run. `resume`: a stopped run whose last link the author has just decided may
    continue with nothing left to check — it then completes without a call."""
    from ..authoring.blueprints import get_role_settings
    from ..providers.policy import request_rating
    from ..rating.guard import enforce_edition_limit
    from .audit_context import MISSING_LINK, NOT_CONFIGURED
    from .auditor_settings import resolve_auditor
    from .readiness import _check_model_policy
    result = {'ready': False, 'reason': None, 'roles': {}, 'calls': 0, 'evaluator': None, 'warnings': [], 'links': []}
    try:
        story = repo.get_story(request.story_id)
        if view is None:
            view = repo.context_view(story.id)
        scene = view.scenes.get(request.scene_id) if request.scene_id else None
        if scene is None or getattr(scene, 'trashed_at', None) or scene.story_id != story.id:
            raise ValueError('Оберіть сцену')
        links = pending_links(view, scene.id)
        states = scene_links(view, scene.id)
        # Design §9: the links the run visits, in reading order Z1 → Z2 → Z3, including those that take no call.
        result['links'] = [{'link': link, 'status': states[link].status, 'reason': states[link].reason} for link in links]
        if not links and not resume:
            raise ValueError(ALREADY_VALID if scene_validity(view, scene.id) == 'valid' else MISSING_LINK)
        settings = resolve_auditor(get_role_settings(repo, story.id))
        if settings is None or not settings.provider.model.strip():
            raise ValueError(NOT_CONFIGURED)
        result['roles'] = {'auditor': settings.provider.model_dump(include={'provider', 'model'})}
        result['calls'] = _calls(states, links)
        if result['calls']:
            rated = view.get_story(story.id)
            enforce_edition_limit(rated, view.get_scene(scene.id))
            _check_model_policy(repo, 'auditor', settings.provider, request_rating(view, rated, [scene.id]))
            if settings.provider.provider in {'venice', 'openrouter'} and \
                    repo.billing('summary', scope='story:' + story.id)['limit_nanos'] is None:
                raise ValueError('Спершу задайте явний ліміт бюджету в налаштуваннях')
        result['ready'] = True
    except (ValueError, KeyError) as exc:
        result['reason'] = str(exc) if isinstance(exc, ValueError) else 'Матеріал не знайдено; оновіть сторінку'
    return result


def _finish(coordinator, run, state, error=None):
    run.state = state
    run.error = error
    coordinator._save(run)
    coordinator.event(run.id, 'state', {'state': state, 'error': error})


def _checkpoint(scene_id, link, outcome, verdict_id=None, reason=None) -> dict:
    return {'scene_id': scene_id, 'link': link, 'outcome': outcome, 'verdict_id': verdict_id, 'reason': reason}


def _awaiting_author(scene_id, link, outcome, verdict_id, reason) -> dict:
    """Design §9: `needs_review`, phase `awaiting_author`, with the link to decide."""
    return {**_checkpoint(scene_id, link, outcome, verdict_id, reason), 'phase': 'awaiting_author'}


def _cancelling(coordinator, run) -> bool:
    return coordinator.cancel_event.is_set() or run.state in {'cancellation_requested', 'cancelled'}


def execute(coordinator, run_id: str) -> None:
    from ..authoring.blueprints import get_role_settings
    from .audit import AuditResult, audit_link
    from .audit_context import NOT_CONFIGURED
    from .audit_output import LINK_STAGE
    from .auditor_settings import resolve_auditor
    repo = coordinator.repo
    stale = 0
    while True:
        with coordinator.condition:
            run = coordinator.get_run(run_id)
            if _cancelling(coordinator, run):
                return _finish(coordinator, run, 'cancelled')
            if run.state in {'pause_requested', 'paused'}:
                return _finish(coordinator, run, 'paused')
        scene_id = run.request.scene_id
        view = repo.context_view(run.story_id)
        links = pending_links(view, scene_id)
        if not links:
            with coordinator.condition:
                current = coordinator.get_run(run_id)
                current.cursor = len(current.tasks)
                current.checkpoint = None
                return _finish(coordinator, current, 'completed')
        link = links[0]
        state = scene_links(view, scene_id)[link]
        if state.status == 'discrepancy':  # the author decides the auditor's verdict; checking it again is not free
            verdict = view.link_verdicts.get((scene_id, link, state.fingerprint))
            with coordinator.condition:
                current = coordinator.get_run(run_id)
                coordinator.event(run_id, 'audit_step', {'scene_id': scene_id, 'link': link, 'outcome': 'discrepancy',
                                                         'verdict_id': verdict and verdict.id, 'attempt_id': None})
                current.checkpoint = _awaiting_author(scene_id, link, 'discrepancy', verdict and verdict.id, state.reason)
                return _finish(coordinator, current, 'needs_review')
        settings = resolve_auditor(get_role_settings(repo, run.story_id))
        if settings is None or not settings.provider.model.strip():
            with coordinator.condition:
                current = coordinator.get_run(run_id)
                current.checkpoint = _checkpoint(scene_id, link, 'failed', reason=NOT_CONFIGURED)
                return _finish(coordinator, current, 'failed', NOT_CONFIGURED)
        if _called(state):  # a call may follow
            coordinator.event(run_id, 'stage_started', {'stage': LINK_STAGE[link], 'scene_id': scene_id, 'link': link,
                                                        'model': settings.provider.model,
                                                        'provider': settings.provider.provider, 'streaming': False})
        try:
            result = audit_link(repo, scene_id, link, coordinator.gateway_factory(settings.provider), run_id=run_id,
                                task_cursor=run.cursor, cancel=coordinator.cancel_event)
        except ValidationError:
            raise
        except ValueError as exc:  # a model policy block, a budget refusal, a prompt or rating refusal: shown as is
            if coordinator.cancel_event.is_set():
                raise
            result = AuditResult('failed', None, None, str(exc))
        with coordinator.condition:
            current = coordinator.get_run(run_id)
            coordinator.event(run_id, 'audit_step', {'scene_id': scene_id, 'link': link, 'outcome': result.outcome,
                                                     'verdict_id': result.verdict_id, 'attempt_id': result.attempt_id})
            attempt = repo.get_attempt(result.attempt_id) if result.attempt_id else None
            if attempt is not None:
                coordinator.event(run_id, 'stage_finished', {'attempt_id': attempt.id, 'state': attempt.state,
                                                             'usage': attempt.usage, 'finish_reason': attempt.finish_reason})
            if result.outcome == 'valid':
                stale = 0
                current.checkpoint = None
                coordinator._save(current)
                continue
            if result.outcome == 'stale':
                stale += 1
                if stale < STALE_STEPS:
                    continue
                current.checkpoint = _checkpoint(scene_id, link, 'stale', reason=result.reason)
                return _finish(coordinator, current, 'failed', STALE_LIMIT)
            if result.outcome == 'failed':
                # A cancelled call is the author's stop, not a model failure (its attempt stays `cancelled`).
                if (attempt is not None and attempt.state == 'cancelled') or _cancelling(coordinator, current):
                    current.checkpoint = _checkpoint(scene_id, link, 'cancelled')
                    return _finish(coordinator, current, 'cancelled')
                current.checkpoint = _checkpoint(scene_id, link, 'failed', reason=result.reason)
                return _finish(coordinator, current, 'failed', result.reason)
            # discrepancy / unavailable: the author decides the link, then resumes the run
            if _cancelling(coordinator, current):  # the verdict is written; the author's cancel still wins
                current.checkpoint = _checkpoint(scene_id, link, result.outcome, result.verdict_id, result.reason)
                return _finish(coordinator, current, 'cancelled')
            current.checkpoint = _awaiting_author(scene_id, link, result.outcome, result.verdict_id, result.reason)
            return _finish(coordinator, current, 'needs_review')
