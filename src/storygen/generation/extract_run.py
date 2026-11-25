"""CHARACTER-EXTRACT (R-51): the queue run `character_extract` reads the prose of the book in groups (spec 3.4, 3.7).

On start the run takes a fresh plan (`characters.extract_plan`), which must still match the plan the author saw, and keeps
a checkpoint (phase `reading`): the running state, the groups still to read, the prose versions of the planned scenes,
the calls bound and the cost. A group is read from the prose version pinned at start. Every call is counted in the
checkpoint before it is sent, so the run never makes more than `calls_bound` calls, after a resume or a restart too.

- A failed call (unparseable answer, empty answer, truncated output) is repeated once; a group that fails again is
  halved; a single scene that fails again is skipped («модель не дала відповіді»).
- A group that does not fit with the current catalogue is halved before the call; a single scene is skipped with the reason.
- A provider or budget error stops the run `failed`; resuming reads the same group again within the bound.
- The bound spent with groups left completes the run with a partial proposal; the rest is skipped.
- Cancel completes the run with a partial proposal; pause leaves it `paused` with its checkpoint.

The proposal is published as phase `done` in the checkpoint (`publish`)."""
import hashlib
import json

from pydantic import ValidationError

from ..characters.extract import (
    SKIP_CALLS_EXHAUSTED, SKIP_NO_ANSWER, CatalogueCard, ExtractResponse, ExtractState, SceneMeta, SceneProse,
    apply_group, finalize, short_ids)
from .extract_context import build_extract_context

STAGE = 'character_extract'
CALL_FAILURES = frozenset({'protocol', 'empty_output', 'output_limit'})  # spec 3.4; any other failure stops the run


def proposal_fingerprint(body: dict) -> str:
    """sha256 of the canonical JSON of a proposal without its `fingerprint` key."""
    payload = {key: value for key, value in body.items() if key != 'fingerprint'}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _cancelling(coordinator, run) -> bool:
    return coordinator.cancel_event.is_set() or run.state in {'cancellation_requested', 'cancelled'}


def _finish(coordinator, run, state, error=None):
    run.state = state
    run.error = error
    coordinator._save(run)
    coordinator.event(run.id, 'state', {'state': state, 'error': error})


def _source(view, scene_id) -> dict | None:
    scene = view.scenes.get(scene_id)
    prose_id = scene.heads.get('prose') if scene is not None and not scene.trashed_at else None
    if not prose_id:
        return None
    ref = view.peek_version(prose_id)
    return {'version_id': ref.id, 'sha256': ref.sha256}


def unread_prose_changed(repo, run) -> bool:
    """A scene still to read has another prose head than the one pinned at start (spec 3.7: resume refuses)."""
    checkpoint = run.checkpoint or {}
    if checkpoint.get('phase') != 'reading':
        return False
    view = repo.context_view(run.story_id)
    pinned = checkpoint['source']
    return any((_source(view, scene_id) or {}).get('sha256') != pinned[scene_id]['sha256']
               for group in checkpoint['pending'] for scene_id in group)


def _start(repo, run) -> dict | str:
    """The checkpoint of a fresh plan, or the reason the run cannot start."""
    from ..characters.extract_plan import DEFAULT_GROUP_WORDS, EXTRACT_PLAN_CHANGED, extract_plan
    from ..characters.names import card_names
    from ..storage.scene_cast import view_cards
    from .audit_cost import CLOUD, upper_bound
    from .extract_context import resolve_extractor
    from ..authoring.blueprints import get_role_settings
    group_words = run.request.group_words or DEFAULT_GROUP_WORDS
    view = repo.context_view(run.story_id)
    plan = extract_plan(repo, run.story_id, group_words, view)
    expected = run.request.extract_plan_fingerprint
    if expected is not None and plan['plan_fingerprint'] != expected:
        return EXTRACT_PLAN_CHANGED
    if not plan['ready']:
        return plan['reason']
    cards = view_cards(view)
    order = [scene_id for group in plan['groups'] for scene_id in group]
    state = ExtractState(
        catalogue=[CatalogueCard(ref=card.id, name=card.name, names=card_names(card), existing=True) for card in cards],
        skipped=[(item['scene_id'], item['reason']) for item in plan['skipped']], scene_order=order)
    extractor = resolve_extractor(get_role_settings(repo, run.story_id))
    per_call = upper_bound(repo, extractor, 1)['per_call_usd'] if extractor.provider.provider in CLOUD else None
    return {'phase': 'reading', 'state': state.model_dump(mode='json'), 'pending': plan['groups'], 'retried': False,
            'source': {scene_id: _source(view, scene_id) for scene_id in order},
            'start_cards_version_id': view.get_story(run.story_id).characters_version_id, 'group_words': group_words,
            'calls_bound': plan['calls_bound'], 'cost_nanos': 0, 'per_call_usd': per_call}


def publish(repo, run, partial: bool, exhausted: bool = False) -> dict:
    """The phase `done` checkpoint with the proposal of the groups read so far (spec 4.1). `exhausted`: the calls bound
    is spent, and the scenes still to read are skipped with that reason; on cancel they are simply not read."""
    from ..characters.extract_plan import _has_author_protagonist
    from ..storage.scene_cast import AUTHOR_PROSE, _planned, view_cards
    from .audit_cost import usd
    checkpoint = run.checkpoint
    state = ExtractState.model_validate(checkpoint['state'])
    pending = [scene_id for group in checkpoint['pending'] for scene_id in group]
    if exhausted:
        state.skipped += [(scene_id, SKIP_CALLS_EXHAUSTED) for scene_id in pending]
    unread = set(pending) | {scene_id for scene_id, _ in state.skipped}
    read = [scene_id for scene_id in state.scene_order if scene_id not in unread]
    view = repo.context_view(run.story_id)
    meta = {}
    for scene_id in read:
        scene = view.scenes.get(scene_id)
        if scene is None or scene.trashed_at:
            continue
        prose_id = scene.heads.get('prose')
        manual = bool(prose_id) and view.peek_version(prose_id).kind == AUTHOR_PROSE
        meta[scene_id] = SceneMeta(scene_id, manual and not _planned(scene), list(scene.character_ids))
    try:
        cards = view_cards(view)
    except (ValueError, KeyError, OSError):
        cards = []
    proposal = finalize(state, meta, _has_author_protagonist(cards))
    proposal.update(
        source={'scenes': {scene_id: checkpoint['source'][scene_id] for scene_id in read},
                'start_cards_version_id': checkpoint['start_cards_version_id'], 'group_words': checkpoint['group_words']},
        partial=partial, calls=state.calls, cost_usd=usd(checkpoint['cost_nanos']))
    proposal['fingerprint'] = proposal_fingerprint(proposal)
    return {'phase': 'done', 'proposal': proposal}


def _close(coordinator, run, state, partial, exhausted=False):
    run.checkpoint = publish(coordinator.repo, run, partial, exhausted)
    _finish(coordinator, run, state)


def _cost_nanos(attempt, per_call_usd) -> int:
    """What the call counted in the budget; the per-call upper bound for a cloud call without a settled record."""
    from ..billing.models import money
    accounting = attempt.context.get('accounting') if attempt is not None else None
    counted = accounting.get('counted_nanos') if isinstance(accounting, dict) else None
    if isinstance(counted, int) and not isinstance(counted, bool):
        return counted
    return money(per_call_usd) if per_call_usd is not None else 0


def _save_checkpoint(coordinator, run_id, checkpoint):
    with coordinator.condition:
        current = coordinator.get_run(run_id)
        current.checkpoint = checkpoint
        coordinator._save(current)
        return current


def _halve(checkpoint, ids):
    half = len(ids) // 2
    checkpoint['pending'][0:1] = [ids[:half], ids[half:]]
    checkpoint['retried'] = False


def _skip(checkpoint, state, ids, reason):
    state.skipped.append((ids[0], reason))
    checkpoint['state'] = state.model_dump(mode='json')
    checkpoint['pending'].pop(0)
    checkpoint['retried'] = False


def execute(coordinator, run_id: str) -> None:
    from ..authoring.blueprints import get_role_settings
    from .extract_context import NO_MEMORY_ROLE, resolve_extractor
    from .stages import execute_stage
    repo = coordinator.repo
    with coordinator.condition:
        run = coordinator.get_run(run_id)
        fresh = (run.checkpoint or {}).get('phase') != 'reading'
    if fresh:
        started = _start(repo, run)
        with coordinator.condition:
            current = coordinator.get_run(run_id)
            if isinstance(started, str):
                return _finish(coordinator, current, 'failed', started)
            current.checkpoint = started
            coordinator._save(current)
    while True:
        with coordinator.condition:
            run = coordinator.get_run(run_id)
            if _cancelling(coordinator, run):
                return _close(coordinator, run, 'cancelled', True)
            if run.state in {'pause_requested', 'paused'}:
                return _finish(coordinator, run, 'paused')
            checkpoint = run.checkpoint
            if not checkpoint['pending']:
                return _close(coordinator, run, 'completed', False)
            state = ExtractState.model_validate(checkpoint['state'])
            if state.calls >= checkpoint['calls_bound']:  # spec 3.7: the bound is spent; no resume would stay within it
                return _close(coordinator, run, 'completed', True, exhausted=True)
        ids = checkpoint['pending'][0]
        settings = resolve_extractor(get_role_settings(repo, run.story_id))
        if settings is None:
            with coordinator.condition:
                return _finish(coordinator, coordinator.get_run(run_id), 'failed', NO_MEMORY_ROLE)
        group = [SceneProse(scene_id, checkpoint['source'][scene_id]['version_id'],
                            repo.read_text(checkpoint['source'][scene_id]['version_id'])) for scene_id in ids]
        card_numbers, scene_numbers = short_ids(state, ids)
        built = build_extract_context(repo, run.story_id, settings, state, group, scene_numbers, card_numbers)
        if isinstance(built, str):  # the catalogue grew: halve before the call, skip a single scene; no call is made
            if len(ids) > 1:
                _halve(checkpoint, ids)
            else:
                _skip(checkpoint, state, ids, built)
            _save_checkpoint(coordinator, run_id, checkpoint)
            continue
        state.calls += 1  # counted before the call is sent: an interrupted call still spends the bound
        checkpoint['state'] = state.model_dump(mode='json')
        run = _save_checkpoint(coordinator, run_id, checkpoint)
        coordinator.event(run_id, 'stage_started', {'stage': STAGE, 'scene_id': ids[0], 'scene_ids': ids,
                                                    'model': built.settings.provider.model,
                                                    'provider': built.settings.provider.provider,
                                                    'estimated_tokens': built.estimated_tokens, 'streaming': False})
        try:
            attempt = execute_stage(repo, ids[0], STAGE, built, coordinator.gateway_factory(built.settings.provider),
                                    coordinator.cancel_event, lambda _text: None, run_id, task_cursor=run.cursor)
        except ValidationError:
            raise
        except ValueError as exc:  # a budget refusal, a model policy block: shown as is; resuming reads the group again
            with coordinator.condition:
                current = coordinator.get_run(run_id)
                if _cancelling(coordinator, current):
                    return _close(coordinator, current, 'cancelled', True)
                return _finish(coordinator, current, 'failed', str(exc))
        checkpoint['cost_nanos'] += _cost_nanos(attempt, checkpoint['per_call_usd'])
        with coordinator.condition:
            current = coordinator.get_run(run_id)
            coordinator.event(run_id, 'stage_finished', {'attempt_id': attempt.id, 'state': attempt.state,
                                                         'usage': attempt.usage, 'finish_reason': attempt.finish_reason})
            current.checkpoint = checkpoint
            if attempt.state == 'cancelled' or (attempt.state != 'completed' and _cancelling(coordinator, current)):
                return _close(coordinator, current, 'cancelled', True)
            if attempt.state == 'completed':
                response = ExtractResponse.model_validate(attempt.context['extract_response'])
                state = apply_group(state, response, group, scene_numbers=scene_numbers, card_numbers=card_numbers)
                checkpoint['state'] = state.model_dump(mode='json')
                checkpoint['pending'].pop(0)
                checkpoint['retried'] = False
            elif (attempt.context.get('extract_failure') or {}).get('category') in CALL_FAILURES:
                if not checkpoint['retried']:
                    checkpoint['retried'] = True
                elif len(ids) > 1:
                    _halve(checkpoint, ids)
                else:
                    _skip(checkpoint, state, ids, SKIP_NO_ANSWER)
            else:  # spec 3.7: a provider or network error stops the run; it can be resumed
                coordinator._save(current)
                return _finish(coordinator, current, 'failed', attempt.error)
            coordinator._save(current)
