import json
import os
import threading
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from ..authoring.blueprints import get_role_settings
from ..domain import DomainModel, RevisionConflict, StageAttempt, new_id, now
from ..providers.streaming import build_generation_gateway
from .context import build_context, make_context, ContextOverflow
from .events import RunEvent
from .pipeline import STAGES, STAGE_ROLES
from .stages import execute_stage


class RunRequest(DomainModel):
    story_id: str
    scene_id: str | None = None
    mode: Literal['stage','scene','remaining','prepare','rebuild_memory','evaluate'] = 'scene'
    stage: Literal['brief','draft','edit','memory'] | None = None
    pause_after: list[Literal['brief','draft','edit','memory']] = Field(default_factory=list)
    evaluation_mode: Literal['scene','edit_pair','story'] = 'scene'

    @model_validator(mode='after')
    def valid(self):
        if self.mode in {'stage','scene','remaining','rebuild_memory'} and not self.scene_id:
            raise ValueError('Оберіть початкову сцену')
        if self.mode=='stage' and not self.stage:
            raise ValueError('Оберіть етап')
        return self


class Run(DomainModel):
    id: str
    story_id: str
    request_id: str
    request: RunRequest
    state: str = 'queued'
    tasks: list[dict]
    cursor: int = 0
    error: str | None = None
    created_at: str = Field(default_factory=now)


class AppInstanceLock:
    def __init__(self,root: Path):
        self.path=root/'worker.lock'
        self.handle=None

    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.handle=self.path.open('a+b')
        try:
            self.handle.seek(0)
            if not self.handle.read(1):
                self.handle.write(b'0');self.handle.flush()
            self.handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.handle.close();self.handle=None
            raise RuntimeError('Цей каталог даних уже відкрито іншим виконавцем') from None
        return self

    def __exit__(self,*args):
        if self.handle:
            self.handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle,fcntl.LOCK_UN)
            self.handle.close();self.handle=None


TERMINAL={'completed','failed','cancelled','interrupted','needs_review','alternative','paused'}


class RunCoordinator:
    def __init__(self,repo,gateway_factory=None,evaluator_factory=None):
        self.repo=repo
        self.gateway_factory=gateway_factory or build_generation_gateway
        from ..evaluation.gateway import build_gateway
        self.evaluator_factory=evaluator_factory or build_gateway
        self.condition=threading.Condition(threading.RLock())
        self.shutdown=threading.Event()
        self.cancel_event=threading.Event()
        self.active_id=None
        self.thread=None
        self.lock=AppInstanceLock(repo.root)

    def get_run(self,id: str) -> Run:
        with self.repo.db.connection() as db:
            return self.repo._get(db,'runs',id,Run)

    def list_runs(self,story_id=None):
        with self.repo.db.connection() as db:
            runs=[Run.model_validate_json(row[0]) for row in db.execute('SELECT payload FROM runs ORDER BY rowid')]
        return [r for r in runs if story_id is None or r.story_id==story_id]

    def _save(self,run):
        with self.repo.db.connection() as db:
            db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(run.state,run.model_dump_json(),run.id))
        return run

    def event(self,id,type,data):
        with self.repo.db.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            seq=db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?',(id,)).fetchone()[0]
            event=RunEvent(run_id=id,seq=seq,type=type,data=data)
            db.execute('INSERT INTO run_events VALUES(?,?,?,?)',(id,seq,type,event.model_dump_json()))
        return event

    def list_events(self,id,after_seq=0):
        self.get_run(id)
        with self.repo.db.connection() as db:
            return [RunEvent.model_validate_json(row[0]) for row in db.execute('SELECT payload FROM run_events WHERE run_id=? AND seq>? ORDER BY seq',(id,after_seq))]

    def enqueue(self,request: RunRequest,request_id: str) -> Run:
        if not request_id or len(request_id)>200:
            raise ValueError('Потрібен request_id до 200 символів')
        self.repo.get_story(request.story_id)
        scenes=self.repo.list_scenes(request.story_id)
        if request.scene_id and request.scene_id not in {s.id for s in scenes}:
            raise ValueError('Сцена не належить цьому твору')
        if request.mode=='prepare':
            tasks=[{'scene_id':None,'stage':'prepare'}]
        elif request.mode=='evaluate':
            tasks=[{'scene_id':request.scene_id,'stage':'evaluate'}]
        else:
            start=next(s for s in scenes if s.id==request.scene_id)
            targets=[start] if request.mode in {'stage','scene'} else [s for s in scenes if s.position>=start.position]
            stages=[request.stage] if request.mode=='stage' else ['memory'] if request.mode=='rebuild_memory' else STAGES
            tasks=[{'scene_id':s.id,'stage':stage} for s in targets for stage in stages]
            if request.mode in {'scene','remaining'}:
                from ..evaluation.story_adapter import get_evaluation_settings
                try:
                    evaluation=get_evaluation_settings(self.repo,request.story_id)
                except ValueError:
                    evaluation=None
                if evaluation and evaluation.policy!='off':
                    expanded=[]
                    for task in tasks:
                        expanded.append(task)
                        if task['stage']=='memory':expanded.append({'scene_id':task['scene_id'],'stage':'evaluate','evaluation_mode':'edit_pair'})
                    tasks=expanded
        with self.condition:
            with self.repo.db.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                existing=db.execute('SELECT payload FROM runs WHERE request_id=?',(request_id,)).fetchone()
                if existing:
                    run=Run.model_validate_json(existing[0])
                    if run.request!=request:
                        raise RevisionConflict('request_id уже використано для іншого запиту')
                    return run
                if request.mode!='evaluate':
                    from .readiness import preview
                    readiness=preview(self.repo,request)
                    if not readiness['ready']:
                        raise ValueError(readiness['reason'])
                self.repo._active_story(db,request.story_id)
                if request.scene_id:self.repo._active_scene(db,request.scene_id)
                run=Run(id=new_id(),story_id=request.story_id,request_id=request_id,request=request,tasks=tasks)
                db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(run.id,run.story_id,request_id,run.state,run.model_dump_json()))
            self.event(run.id,'state',{'state':'queued'})
            self.condition.notify_all()
        return run

    def readiness(self,story_id,scene_id=None):
        from .readiness import preview
        self.repo.get_story(story_id)
        operations={}
        for name in ['prepare',*STAGES,'scene','remaining','rebuild_memory']:
            # model_construct permits the unselected-scene state in a read-only preview.
            request=RunRequest.model_construct(story_id=story_id,scene_id=scene_id,mode='stage' if name in STAGES else name,stage=name if name in STAGES else None)
            operations[name]=preview(self.repo,request)
        return {'operations':operations}

    def run_readiness(self,id):
        from .readiness import pending_preview
        return pending_preview(self.repo,self.get_run(id))

    def pause(self,id):
        with self.condition:
            run=self.get_run(id)
            if run.state not in {'queued','running','pause_requested'}:
                return run
            run.state='pause_requested' if id==self.active_id else 'paused'
            self._save(run);self.event(id,'state',{'state':run.state})
            return run

    def cancel(self,id):
        with self.condition:
            run=self.get_run(id)
            if run.state=='completed':
                return run
            if id==self.active_id:
                run.state='cancellation_requested';self.cancel_event.set()
            else:
                run.state='cancelled'
            self._save(run);self.event(id,'state',{'state':run.state})
            return run

    def resume(self,id,repeat_interrupted=False):
        with self.condition:
            run=self.get_run(id)
            if run.state not in TERMINAL-{'completed'}:
                raise ValueError('Запуск ще виконується')
            attempts=self.repo.list_attempts(run.story_id,run.id)
            task=run.tasks[run.cursor] if run.cursor<len(run.tasks) else None
            latest={}
            for attempt in attempts:
                if task and attempt.stage==task['stage'] and attempt.scene_id==task.get('scene_id') and attempt.context.get('run_cursor',run.cursor)==run.cursor:
                    latest[attempt.context.get('checkpoint_key','stage')]=attempt
            uncertain=[a for a in latest.values() if a.state in {'running','interrupted','failed','cancelled'}]
            if task and task['stage']=='evaluate' and not latest and any(e.type=='stage_started' and e.data.get('stage')=='evaluate' for e in self.list_events(id)):
                uncertain.append(True)  # Legacy evaluator runs before persisted attempts also need explicit repeat.
            if uncertain and not repeat_interrupted:
                raise ValueError('Потрібне явне рішення повторити перерваний або невдалий етап')
            result=self.run_readiness(id)
            if not result['ready']:raise ValueError(result['reason'])
            run.state='queued';run.error=None
            with self.repo.db.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                self.repo._active_story(db,run.story_id)
                if run.request.scene_id:self.repo._active_scene(db,run.request.scene_id)
                db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(run.state,run.model_dump_json(),run.id))
            self.event(id,'state',{'state':run.state});self.condition.notify_all()
            return run

    def recover_interrupted(self):
        recovered=[]
        with self.condition:
            for run in self.list_runs():
                if run.state in {'running','cancellation_requested','pause_requested','queued'}:
                    run.state='interrupted';run.error='Попередню сесію перервано. Автоматичного повтору запитів немає.'
                    self._save(run);self.event(run.id,'state',{'state':run.state});recovered.append(run)
            with self.repo.db.connection() as db:
                rows=db.execute("SELECT payload FROM stage_attempts WHERE state='running'").fetchall()
            for row in rows:
                attempt=StageAttempt.model_validate_json(row[0]);attempt.state='interrupted';self.repo.save_attempt(attempt)
        return recovered

    def start(self):
        self.lock.__enter__()  # Lock before recovery can touch another process's runs.
        try:
            self.recover_interrupted()
            self.shutdown.clear()
            self.thread=threading.Thread(target=self._loop,name='storygen-worker',daemon=True)
            self.thread.start()
        except BaseException:
            self.lock.__exit__();raise

    def stop(self):
        self.shutdown.set();self.cancel_event.set()
        with self.condition:self.condition.notify_all()
        if self.thread:self.thread.join(timeout=5)

    def _loop(self):
        try:
            while not self.shutdown.is_set():
                with self.condition:
                    queued=next((r for r in self.list_runs() if r.state=='queued'),None)
                    if queued is None:
                        self.condition.wait(timeout=.5);continue
                    self.active_id=queued.id;self.cancel_event.clear()
                    queued.state='running';self._save(queued)
                    self.event(queued.id,'state',{'state':'running'})
                try:
                    self._execute(queued.id)
                except Exception as exc:
                    with self.condition:
                        run=self.get_run(queued.id)
                        run.state='cancelled' if self.cancel_event.is_set() else 'failed'
                        run.error=str(exc) if isinstance(exc,ContextOverflow) else 'Етап зупинено. Перевірте контекст, конфігурацію й збережені спроби; автоматичного повтору немає.'
                        self._save(run);self.event(run.id,'state',{'state':run.state,'error':run.error})
                finally:
                    with self.condition:self.active_id=None
        finally:
            self.lock.__exit__()

    def _execute(self,id):
        while True:
            with self.condition:
                run=self.get_run(id)
                if self.cancel_event.is_set():
                    run.state='cancelled';self._save(run);self.event(id,'state',{'state':run.state});return
                if run.state=='pause_requested':
                    run.state='paused';self._save(run);self.event(id,'state',{'state':run.state});return
                if run.cursor>=len(run.tasks):
                    run.state='completed';self._save(run);self.event(id,'state',{'state':run.state});return
                task=run.tasks[run.cursor]
            scene_id,stage=task['scene_id'],task['stage']
            if stage=='evaluate':
                self._evaluate(run)
                if self.get_run(id).state=='running':continue
                return
            roles=get_role_settings(self.repo,run.story_id)
            if STAGE_ROLES[stage] not in roles:
                raise ValueError('Роль не налаштовано')
            role=roles[STAGE_ROLES[stage]]
            if stage=='prepare':
                story=self.repo.get_story(run.story_id)
                sources=[s for s in [self.repo.active_source(story.id,'source_plan'),self.repo.active_source(story.id,'source_characters')] if s]
                context=make_context(self.repo,story,None,stage,role,[f'ДЖЕРЕЛО [version_id={v.id}]\n'+self.repo.read_text(v.id) for v in sources],[v.id for v in sources])
            else:
                context=build_context(self.repo,scene_id,stage,role)
                # Reuse only the selected completed stage with exactly matching source/config input.
                scene=self.repo.get_scene(scene_id)
                head={'brief':'brief','draft':'draft','edit':'prose','memory':'memory'}[stage]
                selected=scene.heads.get(head)
                reuse=None
                if run.request.mode!='stage' and selected and not self.repo.get_version(selected).stale:
                    reuse=next((a for a in reversed(self.repo.list_attempts(run.story_id)) if a.result_version_id==selected and a.state=='completed' and a.context['fingerprint']==context.fingerprint),None)
                    if stage=='brief' and not any(a.result_version_id==selected for a in self.repo.list_attempts(run.story_id)):
                        # An explicitly saved/accepted author brief is authoritative until a dependency changes.
                        with self.condition:
                            current=self.get_run(id);current.cursor+=1;self._save(current)
                            self.event(id,'reused',{'version_id':selected,'stage':stage,'scene_id':scene_id,'author_version':True})
                        continue
                if reuse:
                    with self.condition:
                        current=self.get_run(id);current.cursor+=1;self._save(current)
                        self.event(id,'reused',{'attempt_id':reuse.id,'stage':stage,'scene_id':scene_id})
                    continue
            self.event(id,'stage_started',{'stage':stage,'scene_id':scene_id,'model':role.provider.model,'provider':role.provider.provider,'estimated_tokens':context.estimated_tokens})
            attempt=execute_stage(self.repo,scene_id,stage,context,self.gateway_factory(role.provider),self.cancel_event,lambda text:self.event(id,'delta',{'text':text,'stage':stage,'scene_id':scene_id}),id,task_cursor=run.cursor)
            with self.condition:
                current=self.get_run(id)
                self.event(id,'stage_finished',{'attempt_id':attempt.id,'state':attempt.state,'usage':attempt.usage,'finish_reason':attempt.finish_reason})
                if attempt.state!='completed':
                    current.state=attempt.state;current.error=attempt.error;self._save(current)
                    self.event(id,'state',{'state':current.state,'error':current.error});return
                current.cursor+=1
                if self.cancel_event.is_set():current.state='cancellation_requested'
                elif current.state=='pause_requested' or stage in current.request.pause_after:current.state='pause_requested'
                self._save(current)

    def _evaluate(self,run):
        from ..evaluation.story_adapter import execute_evaluation, get_evaluation_settings
        if get_evaluation_settings(self.repo,run.story_id).policy=='off':
            with self.condition:
                current=self.get_run(run.id);current.cursor+=1;self._save(current)
                self.event(run.id,'evaluation_skipped',{'reason':'Оцінювач вимкнено'})
            return
        execute_evaluation(self,run)
