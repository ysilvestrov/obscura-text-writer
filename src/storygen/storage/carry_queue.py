"""MEMORY-CARRY in storage: the carry run is queued by the transaction that changes a memory head; carry runs are read
into the context view with the rest of the story."""
from ..domain import Scene, new_id
from ..run_models import Run, RunEvent, RunRequest

ACTIVE = ('queued', 'running', 'pause_requested', 'cancellation_requested')


def load_carry_runs(db, story_id: str) -> list[Run]:
    """Active carry runs of the story and finished ones that recorded a failed scene, in queue order."""
    rows = db.execute(
        "SELECT payload FROM runs WHERE story_id=? AND json_extract(payload,'$.request.mode')='memory_carry' "
        "AND (state IN (?,?,?,?) OR json_extract(payload,'$.checkpoint.failed_scene_id') IS NOT NULL) ORDER BY rowid",
        (story_id, *ACTIVE))
    return [Run.model_validate_json(row[0]) for row in rows]


def enqueue_carry(db, scene: Scene, memory_id: str) -> Run | None:
    """On the open transaction of a new memory head (author or stage): a carry run over the later scenes when one of
    them has memory. An active carry run that has not passed the first later scene already covers it; one that has
    passed it is superseded by the new run (it stops itself at its next step)."""
    scenes = [Scene.model_validate_json(row[0]) for row in db.execute(
        'SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id', (scene.story_id,))]
    active = [s for s in scenes if not s.trashed_at]
    later = [s for s in active if s.position > scene.position]
    if not any(s.heads.get('memory') for s in later):
        return None
    request_id = 'carry:' + memory_id
    if db.execute('SELECT 1 FROM runs WHERE request_id=?', (request_id,)).fetchone():
        return None
    start = later[0]
    position = {s.id: s.position for s in active}
    for run in load_carry_runs(db, scene.story_id):
        if run.state not in ACTIVE:
            continue
        ahead = [task['scene_id'] for task in run.tasks[run.cursor:] if task.get('scene_id') in position]
        if ahead and position[ahead[0]] <= start.position:
            return run
    run = Run(id=new_id(), story_id=scene.story_id, request_id=request_id,
              request=RunRequest(story_id=scene.story_id, scene_id=start.id, mode='memory_carry'),
              tasks=[{'scene_id': s.id, 'stage': 'memory_carry'} for s in later],
              planned_telemetry={'roles': {}, 'calls': 0})
    db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (run.id, run.story_id, run.request_id, run.state, run.model_dump_json()))
    event = RunEvent(run_id=run.id, seq=1, type='state', data={'state': 'queued'})
    db.execute('INSERT INTO run_events VALUES(?,?,?,?)', (run.id, 1, 'state', event.model_dump_json()))
    return run
