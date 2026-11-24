"""Видимий прогрес запуску (PROGRESS-UX §2): рахунок викликів, витрати, поточна сцена й крок.

Прогрес обчислюється з подій `stage_started`, `stage_finished` і `audit_step` та збереженого запуску; подія `delta`
не читається. Один словник живить і `GET /api/runs/{id}['progress']`, і подію `progress`.
"""
import math
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

PROGRESS_EVENTS = ('stage_started', 'stage_finished', 'audit_step')
_CENT = Decimal('0.0001')
UNBILLED_STATES = ('failed',)


def usage_usd(usage):
    """Те саме правило, що JS `usageUsd`: `cost` число або `cost.usd`, скінченне."""
    cost = usage.get('cost') if isinstance(usage, dict) else None
    value = cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else (cost.get('usd') if isinstance(cost, dict) else None)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def visited_scene_ids(events):
    seen = []
    for event in events:
        if event.type in ('stage_started', 'audit_step'):
            scene_id = event.data.get('scene_id')
            if scene_id and scene_id not in seen:
                seen.append(scene_id)
    return seen


def _calls(events):
    by_attempt = {}
    for event in events:
        if event.type == 'stage_finished':
            # an event without attempt_id gets a positional key: a replay of it is not deduplicated
            key = event.data.get('attempt_id') or f'call-{len(by_attempt)}'
            price = usage_usd(event.data.get('usage'))
            # A failed attempt without a price was not billed, so it adds $0 (it still counts as a call). A cancelled
            # non-streamed call is billed late by the provider (`_settle_late` writes only to billing), so a cancelled,
            # completed or legacy (no state) attempt without a usable price makes the spend unknown.
            if price is None and event.data.get('state') in UNBILLED_STATES:
                price = 0.0
            by_attempt.setdefault(key, price)
    return by_attempt


def _stopped(run):
    checkpoint = run.checkpoint or {}
    if run.state == 'needs_review' and checkpoint.get('scene_id'):
        return {'scene_id': checkpoint['scene_id'], 'link': checkpoint.get('link'), 'outcome': checkpoint.get('outcome')}
    return None


def _audit_position(run, events):
    request = run.request
    if request.audit_scope == 'scene':
        return {'id': request.scene_id, 'index': 1, 'total': 1}
    visited = visited_scene_ids(events)
    latest = [e.data['scene_id'] for e in events if e.type in ('stage_started', 'audit_step') and e.data.get('scene_id')]
    return {'id': latest[-1] if latest else None, 'index': len(visited), 'total': (run.planned_telemetry or {}).get('scenes')}


def _generation_position(run):
    if not run.tasks:
        return None, None
    task = run.tasks[min(run.cursor, len(run.tasks) - 1)]
    scenes = list(dict.fromkeys(t['scene_id'] for t in run.tasks if t.get('scene_id')))
    scene = None
    if task.get('scene_id'):
        scene = {'id': task['scene_id'], 'index': scenes.index(task['scene_id']) + 1, 'total': len(scenes)}
    return scene, {'stage': task['stage']}


def progress_from_events(run, events):
    if run.request.mode == 'memory_carry':
        return None
    planned = run.planned_telemetry or {}
    calls = _calls(events)
    spent = sum((Decimal(str(v)) for v in calls.values() if v is not None), Decimal('0'))
    if run.request.mode == 'audit':
        scene = _audit_position(run, events)
        marks = [e for e in events if e.type in ('stage_started', 'audit_step') and e.data.get('link')]
        step = {'link': marks[-1].data['link']} if marks else None
    else:
        scene, step = _generation_position(run)
    return {
        'calls': {'done': len(calls), 'planned': planned.get('calls')},
        'spent_usd': str(spent.quantize(_CENT, rounding=ROUND_HALF_UP)),
        'spent_known': all(v is not None for v in calls.values()),
        'bound_usd': planned.get('cost_bound_usd'),
        'scene': scene,
        'step': step,
        'stopped': _stopped(run),
    }


def run_progress(repo, run):
    return progress_from_events(run, repo.list_run_events(run.id, types=PROGRESS_EVENTS))


def emit_progress(coordinator, run_id):
    data = run_progress(coordinator.repo, coordinator.repo.get_run(run_id))
    if data is not None:
        coordinator.event(run_id, 'progress', data)


def extend_plan(plan, progress, readiness, visited):
    """Доповнює план запуску при продовженні (PROGRESS-UX §1): виконані виклики плюс виклики перегляду продовження."""
    if plan is None or not readiness.get('calls', 0):
        return plan
    extended = dict(plan)
    extended['calls'] = progress['calls']['done'] + readiness['calls']
    if 'cost_bound_usd' in plan:
        total = (readiness.get('cost') or {}).get('total_usd')
        if progress['spent_known'] and total is not None:
            bound = Decimal(progress['spent_usd']) + Decimal(str(total))
            extended['cost_bound_usd'] = str(bound.quantize(_CENT, rounding=ROUND_CEILING))
        else:
            extended['cost_bound_usd'] = None
    if 'scenes' in plan:
        fresh = {link['scene_id'] for link in readiness.get('links') or [] if link.get('scene_id')} - set(visited)
        extended['scenes'] = len(visited) + len(fresh)
    return extended
