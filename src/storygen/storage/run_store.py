from ..domain import RevisionConflict, StageAttempt
from ..run_models import Run, RunEvent


def get_run(repo, id):
    with repo.db.connection() as db:
        return repo._get(db, 'runs', id, Run)


def list_runs(repo, story_id=None):
    with repo.db.connection() as db:
        runs = [Run.model_validate_json(row[0]) for row in db.execute('SELECT payload FROM runs ORDER BY rowid')]
        return [r for r in runs if story_id is None or r.story_id == story_id]


def save_run(repo, run):
    with repo.db.connection() as db:
        db.execute('UPDATE runs SET state=?,payload=? WHERE id=?', (run.state, run.model_dump_json(), run.id))
    return run


def requeue_run(repo, run):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        repo._active_story(db, run.story_id)
        if run.request.scene_id:
            scene = repo._active_scene(db, run.request.scene_id)
            if scene.story_id != run.story_id:
                raise ValueError('Сцена належить іншому твору')
        db.execute('UPDATE runs SET state=?,payload=? WHERE id=?', (run.state, run.model_dump_json(), run.id))
    return run


def find_run_by_request_id(repo, request_id):
    with repo.db.connection() as db:
        row = db.execute('SELECT payload FROM runs WHERE request_id=?', (request_id,)).fetchone()
        return Run.model_validate_json(row[0]) if row else None


def enqueue_run(repo, candidate):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT payload FROM runs WHERE request_id=?', (candidate.request_id,)).fetchone()
        if existing:
            run = Run.model_validate_json(existing[0])
            if run.request != candidate.request:
                raise RevisionConflict('request_id уже використано для іншого запиту')
            return run, False
        repo._active_story(db, candidate.story_id)
        if candidate.story_id != candidate.request.story_id:
            raise ValueError('Запит належить іншому твору')
        if candidate.request.scene_id:
            scene = repo._active_scene(db, candidate.request.scene_id)
            if scene.story_id != candidate.story_id:
                raise ValueError('Сцена належить іншому твору')
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (candidate.id, candidate.story_id, candidate.request_id, candidate.state, candidate.model_dump_json()))
        return candidate, True


def append_run_event(repo, run_id, type, data):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        repo._get(db, 'runs', run_id, Run)
        seq = db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?', (run_id,)).fetchone()[0]
        event = RunEvent(run_id=run_id, seq=seq, type=type, data=data)
        db.execute('INSERT INTO run_events VALUES(?,?,?,?)', (run_id, seq, type, event.model_dump_json()))
        return event


def list_run_events(repo, run_id, after_seq=0):
    with repo.db.connection() as db:
        repo._get(db, 'runs', run_id, Run)
        return [RunEvent.model_validate_json(row[0]) for row in db.execute('SELECT payload FROM run_events WHERE run_id=? AND seq>? ORDER BY seq', (run_id, after_seq))]


def recover_running_attempts(repo):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        attempts = [StageAttempt.model_validate_json(row[0]) for row in db.execute("SELECT payload FROM stage_attempts WHERE state='running'")]
        for attempt in attempts:
            attempt.state = 'interrupted'
            db.execute('UPDATE stage_attempts SET state=?,payload=? WHERE id=?', (attempt.state, attempt.model_dump_json(), attempt.id))


def continue_after_acceptance(repo, id, version_id, expected_cursor, expected_scene_revision, acceptance_id=None):
    from .context_view import ContextView
    from ..evaluation_identity import block_key
    from types import SimpleNamespace
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        run=repo._get(db,'runs',id,Run)
        if run.state not in {'alternative','needs_review'} or run.cursor!=expected_cursor or run.cursor>=len(run.tasks):
            raise RevisionConflict('Стан або етап запуску змінено')
        task=run.tasks[run.cursor]
        heads={'brief':'brief','draft':'draft','edit':'prose','memory':'memory'}
        kinds={'brief':'brief','draft':'draft','edit':'edited','memory':'memory'}
        if task['stage'] not in heads or not task.get('scene_id'):
            raise ValueError('Цей етап не підтримує продовження після прийняття')
        scene=repo._active_scene(db,task['scene_id'])
        if scene.story_id!=run.story_id or scene.revision!=expected_scene_revision:
            raise RevisionConflict('Сцену змінено після прийняття')
        view=ContextView(repo,db,run.story_id)
        ref=view.get_version(version_id)
        if ref.scene_id!=scene.id or ref.kind!=kinds[task['stage']] or not ref.complete or ref.stale or scene.heads.get(heads[task['stage']])!=ref.id:
            raise ValueError('Потрібен саме актуальний вибраний результат цього етапу')
        view.read_text(ref.id)
        attempts=[StageAttempt.model_validate_json(r[0]) for r in db.execute('SELECT payload FROM stage_attempts WHERE run_id=? ORDER BY rowid',(run.id,))]
        matching=[a for a in attempts if a.scene_id==scene.id and a.stage==task['stage'] and a.context.get('run_cursor')==run.cursor]
        if not matching or matching[-1].result_version_id!=ref.id or matching[-1].state not in {'alternative','needs_review','completed'}:
            raise ValueError('Версія не є результатом зупиненого етапу')
        acceptance=view.acceptances.get(ref.id)
        if (acceptance.id if acceptance else None)!=acceptance_id:
            raise RevisionConflict('Авторське рішення змінилося або не підтверджене')
        # Repeat refusal protection inside the same transaction as cursor publication.
        evaluation_row=db.execute('SELECT payload FROM app_settings WHERE key=?',('evaluation:'+run.story_id,)).fetchone()
        if evaluation_row:
            import json
            evaluation=json.loads(evaluation_row[0])
            if evaluation['policy']=='pause_on_failure' and any(t['stage']=='evaluate' for t in run.tasks[run.cursor+1:]):
                config=SimpleNamespace(**evaluation['config'])
                row=db.execute('SELECT payload FROM app_settings WHERE key=?',(block_key(run.story_id,config),)).fetchone()
                if row:
                    raise ValueError('Оцінювач заблоковано для цього оповідання після відмови. '+json.loads(row[0])['failure']['message'])
        old_cursor=run.cursor
        run.cursor+=1
        run.state='queued'
        run.error=None
        db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(run.state,run.model_dump_json(),run.id))
        seq=db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?',(run.id,)).fetchone()[0]
        for offset,(type,data) in enumerate([('continued_after_acceptance',{'version_id':ref.id,'acceptance_id':acceptance_id,'previous_cursor':old_cursor,'cursor':run.cursor}),('state',{'state':run.state})]):
            event=RunEvent(run_id=run.id,seq=seq+offset,type=type,data=data)
            db.execute('INSERT INTO run_events VALUES(?,?,?,?)',(run.id,event.seq,type,event.model_dump_json()))
        return run
