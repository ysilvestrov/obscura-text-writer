"""MEMORY-CARRY in storage: the carry run is queued by the transaction that changes a memory head; carry runs are read
into the context view with the rest of the story."""
from ..domain import Scene, new_id
from ..run_models import Run, RunEvent, RunRequest

ACTIVE = ('queued', 'running', 'pause_requested', 'cancellation_requested')
# A carry stopped before its end that can be resumed: its remaining scenes stay pending while it is the latest carry run.
STALLED = ('paused', 'failed', 'interrupted')


def load_carry_runs(db, story_id: str) -> list[Run]:
    """Active and stalled carry runs of the story, finished ones that recorded a failed scene and the latest carry run,
    in queue order."""
    carry = "story_id=? AND json_extract(payload,'$.request.mode')='memory_carry'"
    rows = db.execute(
        f"SELECT payload FROM runs WHERE {carry} AND (state IN (?,?,?,?,?,?,?) "
        f"OR json_extract(payload,'$.checkpoint.failed_scene_id') IS NOT NULL "
        f"OR rowid=(SELECT MAX(rowid) FROM runs WHERE {carry})) ORDER BY rowid",
        (story_id, *ACTIVE, *STALLED, story_id))
    return [Run.model_validate_json(row[0]) for row in rows]


def enqueue_carry(db, scene: Scene, memory_id: str) -> Run | None:
    """On the open transaction of a new memory head (author or stage): a carry run over the later scenes when one of
    them has memory. An active carry run that has not passed the first later scene already covers it; one that has
    passed it is superseded by the new run (it stops itself at its next step)."""
    # The head revision keeps a version selected again (A → B → A → B) from reusing the finished run of its first time.
    request_id = f"carry:{memory_id}:{scene.head_revisions.get('memory', 0)}"
    return _enqueue(db, scene.story_id, lambda s: s.position > scene.position, request_id)


def enqueue_merge_carry(db, story_id: str, target_ids, version_id: str) -> Run | None:
    """On the open transaction that publishes a memory merge: a carry run from the first scene that starts from the
    merge point, so the journals built on an earlier merge (or stopped before it) extend the new one."""
    targets = set(target_ids)
    return _enqueue(db, story_id, lambda s: s.id in targets, f'carry:merge:{version_id}', from_first=True)


def _enqueue(db, story_id: str, covers, request_id: str, from_first: bool = False) -> Run | None:
    """`covers`: the scenes to carry; with `from_first`, every scene from the first covered one onwards."""
    scenes = [Scene.model_validate_json(row[0]) for row in db.execute(
        'SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id', (story_id,))]
    active = [s for s in scenes if not s.trashed_at]
    later = [s for s in active if covers(s)]
    if from_first and later:
        later = [s for s in active if s.position >= later[0].position]
    if not any(s.heads.get('memory') for s in later):
        return None
    if db.execute('SELECT 1 FROM runs WHERE request_id=?', (request_id,)).fetchone():
        return None
    start = later[0]
    position = {s.id: s.position for s in active}
    for run in load_carry_runs(db, story_id):
        if run.state not in ACTIVE:
            continue
        ahead = [task['scene_id'] for task in run.tasks[run.cursor:] if task.get('scene_id') in position]
        if ahead and position[ahead[0]] <= start.position:
            return run
    run = Run(id=new_id(), story_id=story_id, request_id=request_id,
              request=RunRequest(story_id=story_id, scene_id=start.id, mode='memory_carry'),
              tasks=[{'scene_id': s.id, 'stage': 'memory_carry'} for s in later],
              planned_telemetry={'roles': {}, 'calls': 0})
    db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (run.id, run.story_id, run.request_id, run.state, run.model_dump_json()))
    event = RunEvent(run_id=run.id, seq=1, type='state', data={'state': 'queued'})
    db.execute('INSERT INTO run_events VALUES(?,?,?,?)', (run.id, 1, 'state', event.model_dump_json()))
    return run
