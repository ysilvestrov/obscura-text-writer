"""MEMORY-CARRY: the queue run `memory_carry` — no model and no budget. It walks the later scenes in reading order;
each step is its own transaction with CAS on the scene revision (storage commit_memory_carry)."""
from ..domain import RevisionConflict
import re

from ..memory.carry import ACTIVE, CARRY_MISSING, CarryFailed, carry_journal, same_inheritance
from ..run_models import merge_warnings

STEP_RETRIES = 3
FAILED = 'Перенос пам’яті зупинено на сцені «{p0}»: її записи посилаються на твердження, яких немає в новій пам’яті попередньої сцени — створіть нову пам’ять цієї сцени'
FAILED_REASON = 'Перенос пам’яті зупинено на сцені «{p0}»: {p1} — створіть нову пам’ять цієї сцени'
MERGE_STOP = 'Перенос пам’яті зупинено на сцені «{p0}»: потрібне злиття пам’яті перед цією сценою — підтвердьте злиття'


def stop_warning(title: str, detail: str | None) -> str:
    """The warning of a failed carry step: the general sentence for missing claims or a reason that is not app text
    (a KeyError or a validation message without Ukrainian words), else the real reason on one line."""
    reason = ' '.join((detail or '').split()).rstrip('.')
    if not reason or reason == CARRY_MISSING or not re.search('[А-Яа-яІіЇїЄєҐґ]', reason):
        return FAILED.replace('{p0}', title)
    return FAILED_REASON.replace('{p0}', title).replace('{p1}', reason)


def _carried_snapshot(view, snapshot, before, carried):
    """The scene memory's own snapshot with only the previous memory (its selector and refs) and the journal sources
    replaced: head/prose and every other input stay, so the links of the scene keep their state."""
    if snapshot is None:
        return None, list(dict.fromkeys(carried.source_prose_ids + [before.memory_id]))
    selectors = []
    for selector in snapshot.selectors:
        if before.merge_key and selector.kind == 'story' and selector.field == 'memory_merge_heads':
            selector = selector.model_copy(update={'expected': {before.merge_key: before.memory_id}})
        elif (before.ancestors and not before.merge_key and selector.kind == 'head' and selector.field == 'memory'
              and selector.owner_id == before.ancestors[-1].id):
            selector = selector.model_copy(update={'expected': before.memory_id})
        selectors.append(selector)
    journal_kinds = {'edited', 'manual', 'memory', 'memory_merge', 'series_start'}
    kept = [id for id in snapshot.refs if id in view.versions and view.versions[id].kind not in journal_kinds]
    ids = list(dict.fromkeys(kept + carried.source_prose_ids + [before.memory_id]))
    refs = {id: view.versions[id].sha256 for id in ids}
    snapshot = snapshot.model_copy(update={
        'selectors': selectors, 'refs': refs,
        'ref_baselines': {id: view.acceptances[id].id if id in view.acceptances else None for id in ids},
        'accepted_stale_prose_ids': [id for id in ids if view.versions[id].kind in {'edited', 'manual'}]})
    return snapshot, ids


def carry_step(repo, story_id: str, scene_id: str, run_id: str) -> dict:
    """One scene: `carried`, `current` (nothing to carry), `skipped` (no memory or no previous memory), `failed`
    (the own events do not apply; the memory stays) or `stopped` (a merge before the scene must be confirmed)."""
    from ..memory.journal import load_memory
    from ..memory.previous import previous_memory, read_previous_journal
    from ..memory.series_start import read_source
    from ..memory.story_time import is_flashback
    for _ in range(STEP_RETRIES):
        view = repo.context_view(story_id)
        scene = view.scenes.get(scene_id)
        if scene is None or scene.trashed_at or not scene.heads.get('memory'):
            return {'result': 'skipped'}
        memory_id = scene.heads['memory']
        before = previous_memory(view, scene, peek=True, require=False)
        if before.memory_id is None:
            if before.merge_key:
                return {'result': 'stopped', 'reason': 'merge_required', 'memory_id': memory_id}
            return {'result': 'skipped'}
        try:
            journal = load_memory(view.read_text(memory_id))
            previous = read_previous_journal(view, before)
            if same_inheritance(previous, journal):
                return {'result': 'current'}
            sources = {id: read_source(view, id) for id in previous.source_prose_ids + journal.source_prose_ids[-1:]}
            carried = carry_journal(previous, journal, sources)
            if is_flashback(scene):
                from ..memory.flashbacks import check_flashback_journal
                check_flashback_journal(carried, previous)
        except (CarryFailed, ValueError, KeyError, OSError) as exc:
            return {'result': 'failed', 'reason': 'carry_failed', 'detail': str(exc), 'memory_id': memory_id}
        old = view.versions[memory_id]
        snapshot, refs = _carried_snapshot(view, old.dependency_snapshot, before, carried)
        try:
            version = repo.commit_memory_carry(scene_id, carried.model_dump_json(), carried_from=memory_id,
                                               expected_revision=scene.revision, expected_previous_id=before.memory_id,
                                               input_refs=refs, dependency_snapshot=snapshot, source_run_id=run_id,
                                               memory_confirmation=old.memory_confirmation)
        except RevisionConflict:
            continue  # the author changed the scene meanwhile: read it again; their change stays
        return {'result': 'carried', 'version_id': version.id}
    raise RevisionConflict('Сцену змінювали під час переносу пам’яті кілька разів поспіль; перенос зупинено')


def _superseded(repo, run) -> bool:
    """A later carry run of the story is waiting: it starts from an earlier change and covers this run's scenes."""
    runs = repo.list_runs(run.story_id)
    index = next(i for i, item in enumerate(runs) if item.id == run.id)
    return any(item.request.mode == 'memory_carry' and item.state in ACTIVE for item in runs[index + 1:])


def _finish(coordinator, run, state):
    run.state = state
    coordinator._save(run)
    coordinator.event(run.id, 'state', {'state': state, 'error': run.error})


def execute(coordinator, run_id: str) -> None:
    repo = coordinator.repo
    while True:
        with coordinator.condition:
            run = coordinator.get_run(run_id)
            if coordinator.cancel_event.is_set() or run.state in {'cancellation_requested', 'cancelled'}:
                return _finish(coordinator, run, 'cancelled')
            if run.state == 'pause_requested':
                return _finish(coordinator, run, 'paused')
            if _superseded(repo, run):
                coordinator.event(run.id, 'superseded', {})
                return _finish(coordinator, run, 'cancelled')
            if run.cursor >= len(run.tasks):
                return _finish(coordinator, run, 'completed')
            scene_id = run.tasks[run.cursor]['scene_id']
        outcome = carry_step(repo, run.story_id, scene_id, run.id)
        with coordinator.condition:
            current = coordinator.get_run(run_id)
            coordinator.event(run_id, 'carry_step', {'scene_id': scene_id, **outcome})
            if outcome['result'] in {'failed', 'stopped'}:
                key = 'failed_scene_id' if outcome['result'] == 'failed' else 'stopped_scene_id'
                current.checkpoint = {key: scene_id, **{k: v for k, v in outcome.items() if k != 'result'}}
                scene = repo.get_scene(scene_id)
                text = (stop_warning(scene.title, outcome.get('detail')) if outcome['result'] == 'failed'
                        else MERGE_STOP.replace('{p0}', scene.title))
                current.warning = merge_warnings(current.warning, [text])
                return _finish(coordinator, current, 'completed')
            current.cursor += 1
            coordinator._save(current)
