"""VALID-LINKS: the queue run `audit` for one scene (R-44 PR 3) or for the whole book (R-44 PR 4), design §9.

On every step the worker reads the material again and checks the first link that still needs a check, in reading order
(the scenes of the book by position without the trash, in a scene brief → prose → memory): the author's decisions and
edits change the set between calls, so a book run may go back to an earlier scene. `valid` goes on; `discrepancy` and
`unavailable` stop in `needs_review` with a checkpoint (phase `awaiting_author`, `scene_id` the scene of the stop); a
link that already holds an auditor `discrepancy` stops there with that verdict and no new call, on start and on resume;
an auditor `unavailable` that is not an overflow is measured again without a call and stops the same way while its
cause holds, or is checked like an `unchecked` link once it has cleared; a stale verdict reads the link again (at most
STALE_STEPS times in a row for one scene and link). Pause and cancel act between calls. It is a model run: a restart
leaves it `interrupted`, and a failed call is repeated only on the author's explicit decision (RunCoordinator.resume)."""
import hashlib
import json

from pydantic import ValidationError

from ..storage.links import scene_links, scene_validity

PENDING = ('unchecked', 'discrepancy', 'unavailable')
STALE_STEPS = 3
ALREADY_VALID = 'Сцена вже валідна'
BOOK_VALID = 'Книга вже валідна'
PLAN_CHANGED = 'План перевірки змінився. Перегляньте його ще раз'
STALE_LIMIT = 'Сцену змінювали під час перевірки кілька разів поспіль'


def pending_links(view, scene_id: str) -> list[str]:
    """The links still to check, in reading order brief → prose → memory; `valid` and `missing` are left out."""
    return [link for link, state in scene_links(view, scene_id).items() if state.status in PENDING]


def book_pending(view) -> list[tuple[str, str]]:
    """(scene_id, link) still to check in the whole book, in reading order: scenes by position without the trash."""
    scenes = sorted(view.list_scenes(view.story.id), key=lambda scene: scene.position)
    return [(scene.id, link) for scene in scenes for link in pending_links(view, scene.id)]


def _pending(view, request) -> list[tuple[str, str]]:
    if request.audit_scope == 'story':
        return book_pending(view)
    return [(request.scene_id, link) for link in pending_links(view, request.scene_id)]


def _overflow(reason) -> bool:
    """An auditor verdict that the input did not fit the auditor's limits (audit_context.OVERFLOW_*)."""
    from .audit_context import OVERFLOW_CHARS, OVERFLOW_TOKENS
    return any((reason or '').startswith(text.split('{')[0]) for text in (OVERFLOW_CHARS, OVERFLOW_TOKENS))


def _called(state) -> bool:
    """An `unchecked` link is called; an auditor's overflow verdict is measured again first and may be called. A
    `discrepancy` keeps its verdict until the author decides, and link_state's own `unavailable` gets no call."""
    return state.status == 'unchecked' or (
        state.status == 'unavailable' and state.source == 'auditor' and _overflow(state.reason))


def _measured_again(state) -> bool:
    """An auditor's `unavailable` that is not an overflow (unreadable material, a foreign previous memory): its cause may
    have cleared for the same fingerprint, so it is measured again without a call (_available)."""
    return state.status == 'unavailable' and state.source == 'auditor' and not _overflow(state.reason)


def _available(repo, view, scene_id, link) -> bool:
    """The audit context builds now: the link is checked like an `unchecked` one. A refusal (role, rating) is left to
    the readiness checks and to the call itself, which report it."""
    from .audit_context import AuditUnavailable, build_audit_context
    try:
        return not isinstance(build_audit_context(repo, scene_id, link, view=view), AuditUnavailable)
    except ValueError:
        return True


def _will_call(repo, view, scene_id, link, state) -> bool:
    return _called(state) or (_measured_again(state) and _available(repo, view, scene_id, link))


def plan_fingerprint(scope, scene_id, entries, settings) -> str:
    """sha256 of the canonical plan: `entries` are [scene_id, link, status, link fingerprint] in reading order, and the
    auditor fields that decide what a call costs and returns. A run started from an older preview is refused."""
    provider = settings.provider
    payload = {'scope': scope, 'scene_id': scene_id, 'links': [list(entry) for entry in entries],
               'auditor': {'provider': provider.provider, 'model': provider.model, 'base_url': provider.base_url,
                           'max_input_chars': settings.max_input_chars, 'max_output_tokens': settings.max_output_tokens}}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def readiness(repo, request, view=None, resume=False) -> dict:
    """Read-only preflight of an audit run. `resume`: a stopped run whose last link the author has just decided may
    continue with nothing left to check — it then completes without a call."""
    from ..authoring.blueprints import get_role_settings
    from ..providers.policy import request_rating
    from ..rating.guard import enforce_edition_limit
    from .audit_context import MISSING_LINK, NOT_CONFIGURED
    from .audit_cost import empty, upper_bound
    from .audit_output import LINK_STAGE
    from .auditor_settings import resolve_auditor, validate_auditor_prompt
    from .readiness import _check_model_policy
    book = request.audit_scope == 'story'
    result = {'ready': False, 'reason': None, 'roles': {}, 'calls': 0, 'evaluator': None, 'warnings': [], 'links': [],
              'plan_fingerprint': None, 'cost': empty()}
    if book:
        result['invalid_scenes'] = 0
    try:
        story = repo.get_story(request.story_id)
        if view is None:
            view = repo.context_view(story.id)
        if book:
            pending = book_pending(view)
        else:
            scene = view.scenes.get(request.scene_id) if request.scene_id else None
            if scene is None or getattr(scene, 'trashed_at', None) or scene.story_id != story.id:
                raise ValueError('Оберіть сцену')
            pending = [(scene.id, link) for link in pending_links(view, scene.id)]
        states = {scene_id: scene_links(view, scene_id) for scene_id in dict.fromkeys(s for s, _ in pending)}
        # Design §9: the links the run visits, in reading order, including those that take no call.
        result['links'] = [{**({'scene_id': scene_id} if book else {}), 'link': link,
                            'status': states[scene_id][link].status, 'reason': states[scene_id][link].reason}
                           for scene_id, link in pending]
        if book:
            result['invalid_scenes'] = len(states)  # the scenes the run visits
        if not pending and not resume:
            if book:
                raise ValueError(BOOK_VALID)
            raise ValueError(ALREADY_VALID if scene_validity(view, scene.id) == 'valid' else MISSING_LINK)
        settings = resolve_auditor(get_role_settings(repo, story.id))
        if settings is None or not settings.provider.model.strip():
            raise ValueError(NOT_CONFIGURED)
        result['roles'] = {'auditor': settings.provider.model_dump(include={'provider', 'model'})}
        called = [(scene_id, link) for scene_id, link in pending
                  if _will_call(repo, view, scene_id, link, states[scene_id][link])]
        # An upper bound: an earlier discrepancy or unavailable link stops the run before the later links are called.
        result['calls'] = len(called)
        # Design §9: priced before the refusals below, so a run refused for its limit still shows what it may cost.
        result['cost'] = upper_bound(repo, settings, result['calls'])
        if called:
            # PROMPT-CONTRACT: the prompts of the stages this run may call; context build checks again before each call.
            for stage in dict.fromkeys(LINK_STAGE[link] for _, link in called):
                validate_auditor_prompt(repo, story.id, settings, stage)
            rated = view.get_story(story.id)
            called_scenes = list(dict.fromkeys(scene_id for scene_id, _ in called))
            for scene_id in called_scenes:
                enforce_edition_limit(rated, view.get_scene(scene_id))
            _check_model_policy(repo, 'auditor', settings.provider, request_rating(view, rated, called_scenes))
            if settings.provider.provider in {'venice', 'openrouter'} and \
                    repo.billing('summary', scope='story:' + story.id)['limit_nanos'] is None:
                raise ValueError('Спершу задайте явний ліміт бюджету в налаштуваннях')
        entries = [[scene_id, link, states[scene_id][link].status, states[scene_id][link].fingerprint]
                   for scene_id, link in pending]
        result['plan_fingerprint'] = plan_fingerprint(request.audit_scope, None if book else request.scene_id, entries,
                                                      settings)
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
    last = None
    while True:
        with coordinator.condition:
            run = coordinator.get_run(run_id)
            if _cancelling(coordinator, run):
                return _finish(coordinator, run, 'cancelled')
            if run.state in {'pause_requested', 'paused'}:
                return _finish(coordinator, run, 'paused')
        view = repo.context_view(run.story_id)
        pending = _pending(view, run.request)
        if not pending:
            with coordinator.condition:
                current = coordinator.get_run(run_id)
                current.cursor = len(current.tasks)
                current.checkpoint = None
                return _finish(coordinator, current, 'completed')
        scene_id, link = pending[0]
        if (scene_id, link) != last:  # STALE_STEPS counts the stale verdicts of one scene and link in a row
            stale = 0
            last = (scene_id, link)
        state = scene_links(view, scene_id)[link]
        measured = _measured_again(state)
        # The author decides the auditor's verdict while it still holds; checking it again is not free.
        if state.status == 'discrepancy' or (measured and not _available(repo, view, scene_id, link)):
            verdict = view.link_verdicts.get((scene_id, link, state.fingerprint))
            with coordinator.condition:
                current = coordinator.get_run(run_id)
                coordinator.event(run_id, 'audit_step', {'scene_id': scene_id, 'link': link, 'outcome': state.status,
                                                         'verdict_id': verdict and verdict.id, 'attempt_id': None})
                current.checkpoint = _awaiting_author(scene_id, link, state.status, verdict and verdict.id, state.reason)
                return _finish(coordinator, current, 'needs_review')
        settings = resolve_auditor(get_role_settings(repo, run.story_id))
        if settings is None or not settings.provider.model.strip():
            with coordinator.condition:
                current = coordinator.get_run(run_id)
                current.checkpoint = _checkpoint(scene_id, link, 'failed', reason=NOT_CONFIGURED)
                return _finish(coordinator, current, 'failed', NOT_CONFIGURED)
        if _called(state) or measured:  # a call may follow
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
