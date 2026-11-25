import logging
import threading


from ..authoring.blueprints import get_role_settings
from ..providers.requests import streams
from ..domain import RevisionConflict, new_id
from ..storage.locking import AppInstanceLock
from ..providers.streaming import build_generation_gateway
from .context import build_context, make_context, ContextOverflow
from ..run_models import IMPACT_REMOVED, Run, RunRequest, RunEvent, merge_warnings
from .pipeline import STAGES, STAGE_ROLES
from .run_progress import PROGRESS_EVENTS, emit_progress
from .stages import execute_stage
from ..book.lineage import lineage_scope


TERMINAL={'completed','failed','cancelled','interrupted','needs_review','alternative','paused'}
CANCEL_TRANSITIONS = {
    'queued': 'cancelled',
    'running': 'cancellation_requested',
    'pause_requested': 'cancellation_requested',
    'paused': 'cancelled',
    'interrupted': 'cancelled',
    'needs_review': 'cancelled',
    'alternative': 'cancelled',
}


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
        return self.repo.get_run(id)

    def list_runs(self, story_id: str | None = None) -> list[Run]:
        return self.repo.list_runs(story_id)

    def _save(self,run):
        return self.repo.save_run(run)

    def event(self,id,type,data):
        event=self.repo.append_run_event(id,type,data)
        if type in PROGRESS_EVENTS:
            try:emit_progress(self,id)
            except Exception:logging.getLogger(__name__).exception('Не вдалося обчислити прогрес запуску %s',id)  # progress is advisory: it never fails a run
        return event

    def list_events(self,id,after_seq=0):
        return self.repo.list_run_events(id,after_seq)

    def enqueue(self,request: RunRequest,request_id: str,origin: str | None = None) -> Run:
        skipped_language=[]  # scenes whose automatic evaluation is skipped for their language (STORY-LANGUAGE-S06)
        if not request_id or len(request_id)>200:
            raise ValueError('Потрібен request_id до 200 символів')
        from .edit_pass import resolve_edit_pass_limit
        existing=self.repo.find_run_by_request_id(request_id)
        request=resolve_edit_pass_limit(self.repo,request,existing)
        if existing:
            if existing.request!=request:
                raise RevisionConflict('request_id уже використано для іншого запиту')
            return existing
        self.repo.get_story(request.story_id)
        scenes=self.repo.list_scenes(request.story_id)
        if request.scene_id and request.scene_id not in {s.id for s in scenes}:
            raise ValueError('Сцена не належить цьому твору')
        if request.mode=='impact':
            raise ValueError(IMPACT_REMOVED)
        if request.mode=='rewrite':
            tasks=[{'scene_id':request.scene_id,'stage':'rewrite'}]
        elif request.mode=='publication_suggest':
            tasks=[{'scene_id':None,'stage':'publication_suggest'}]
        elif request.mode=='timeline_summary':
            from .timeline_summary import build_summary_context
            build_summary_context(self.repo,request.story_id,request.summary_block_key)  # refuse before the queue
            tasks=[{'scene_id':None,'stage':'timeline_summary'}]
        elif request.mode=='prepare':
            tasks=[{'scene_id':None,'stage':'prepare'}]
        elif request.mode=='evaluate':
            tasks=[{'scene_id':request.scene_id,'stage':'evaluate'}]
        elif request.mode=='edit_loop':
            tasks=[{'scene_id':request.scene_id,'stage':'edit'} for _ in range(request.edit_pass_limit)]
        elif request.mode=='classify':
            tasks=[{'scene_id':request.scene_id,'stage':'classify'}]
        elif request.mode=='audit':
            tasks=[{'scene_id':request.scene_id,'stage':'audit'}]  # audit_run picks the link (and the scene) on every step
        elif request.mode=='memory_carry':
            start=next(s for s in scenes if s.id==request.scene_id)
            tasks=[{'scene_id':s.id,'stage':'memory_carry'} for s in scenes if s.position>=start.position]
        else:
            start=next(s for s in scenes if s.id==request.scene_id)
            targets=[start] if request.mode in {'stage','scene'} else [s for s in scenes if s.position>=start.position]
            stages=[request.stage] if request.mode=='stage' else ['memory'] if request.mode=='rebuild_memory' else STAGES
            tasks=[{'scene_id':s.id,'stage':stage} for s in targets for stage in stages]
            if request.mode in {'scene','remaining'} and request.edit_workflow=='loop':
                for task in tasks:
                    if task['stage']=='edit':
                        task['editor_loop']=True
            if request.mode in {'scene','remaining'}:
                from ..evaluation.story_adapter import get_evaluation_settings
                try:
                    evaluation=get_evaluation_settings(self.repo,request.story_id)
                except ValueError:
                    evaluation=None
                if evaluation and evaluation.policy!='off':
                    from ..evaluation.story_adapter import evaluated_scenes
                    story=self.repo.get_story(request.story_id)
                    # STORY-LANGUAGE-S06: English prose is not evaluated until the rubric is calibrated for it.
                    english={t['scene_id'] for t in tasks if t['stage']=='memory' and not evaluated_scenes(self.repo,story,scenes,t['scene_id'])}
                    skipped_language=[t['scene_id'] for t in tasks if t['stage']=='memory' and t['scene_id'] in english]
                    expanded=[]
                    for task in tasks:
                        expanded.append(task)
                        if task['stage']=='memory' and task['scene_id'] not in english:
                            expanded.append({'scene_id':task['scene_id'],'stage':'evaluate','evaluation_mode':'edit_pair'})
                    tasks=expanded
        with self.condition:
            existing=self.repo.find_run_by_request_id(request_id)
            if existing:
                if existing.request!=request:
                    raise RevisionConflict('request_id уже використано для іншого запиту')
                return existing
            if request.mode=='publication_suggest' and any(
                r.request.mode=='publication_suggest' and r.state in {'queued','running','pause_requested','cancellation_requested'}
                for r in self.list_runs(request.story_id)
            ):
                raise ValueError('Пропозиція картки публікації вже виконується')
            if request.mode=='timeline_summary' and any(
                r.request.mode=='timeline_summary' and r.request.summary_block_key==request.summary_block_key
                and r.state in {'queued','running','pause_requested','cancellation_requested'}
                for r in self.list_runs(request.story_id)
            ):
                raise ValueError('Підсумок цього блоку вже створюється')
            if request.mode == 'classify' and any(
                r.request.mode == 'classify'
                and r.request.proposal_attempt_id == request.proposal_attempt_id
                and r.state in {'queued', 'running', 'pause_requested', 'cancellation_requested'}
                for r in self.list_runs(request.story_id)
            ):
                raise ValueError('Класифікація цієї пропозиції вже виконується')
            if request.mode == 'edit_loop' and any(
                r.request.mode == 'edit_loop'
                and r.request.scene_id == request.scene_id
                and r.state in {'queued', 'running', 'pause_requested', 'cancellation_requested'}
                for r in self.list_runs(request.story_id)
            ):
                raise ValueError('Багатопрохідна редактура цієї сцени вже виконується')
            readiness=None
            if request.mode == 'evaluate':
                from ..evaluation.story_adapter import get_evaluation_settings
                from ..evaluation.blocks import require_available
                evaluation = get_evaluation_settings(self.repo, request.story_id)
                if evaluation.policy == 'off':
                    raise ValueError('Оцінювання вимкнено')
                require_available(self.repo, request.story_id, evaluation.config)
            else:
                from .readiness import preview
                readiness=preview(self.repo,request)
                if not readiness['ready']:
                    raise ValueError(readiness['reason'])
                if request.mode=='audit' and request.audit_plan_fingerprint is not None and \
                        request.audit_plan_fingerprint!=readiness.get('plan_fingerprint'):
                    from .audit_run import PLAN_CHANGED
                    raise RevisionConflict(PLAN_CHANGED)  # the author saw another plan: nothing is queued or paid
                if request.mode=='rebuild_memory' and request.memory_plan_fingerprint is not None and \
                        request.memory_plan_fingerprint!=readiness.get('plan_fingerprint'):
                    from .memory_build import MEMORY_PLAN_CHANGED
                    raise RevisionConflict(MEMORY_PLAN_CHANGED)
            telemetry={'roles':readiness.get('roles',{}),'calls':readiness.get('calls')} if readiness is not None else None
            if telemetry is not None and readiness.get('evaluator'):
                telemetry['evaluator']=readiness['evaluator']
            if telemetry is not None and request.mode=='audit':
                telemetry['cost_bound_usd']=(readiness.get('cost') or {}).get('total_usd')
                if request.audit_scope=='story':
                    telemetry['scenes']=readiness.get('invalid_scenes')
            candidate=Run(id=new_id(),story_id=request.story_id,request_id=request_id,request=request,tasks=tasks,planned_telemetry=telemetry,origin=origin)
            run,created=self.repo.enqueue_run(candidate)
            if created:
                self.event(run.id,'state',{'state':'queued'})
                self._supersede(run)
                from ..evaluation.story_adapter import ENGLISH_NOT_EVALUATED
                for scene_id in skipped_language:
                    self.event(run.id,'evaluation_skipped',{'scene_id':scene_id,'reason':ENGLISH_NOT_EVALUATED})
            self.condition.notify_all()
        return run

    def _supersede(self,new: Run) -> None:
        """RUN-SUPERSEDE: a new run of one stage of a scene cancels stopped runs waiting at that same stage of that scene;
        a new book validation cancels every resumable audit run of that story, so no older plan is paid on resume
        (VALID-RUN). A book validation the MCP bridge started cancels only resumable audits the bridge started: the chat may
        not cancel the author's runs (guard_bridge_cancel), so it does not drop the author's stopped check either."""
        if new.request.mode=='audit' and new.request.audit_scope=='story':
            for run in self.list_runs(new.story_id):
                if run.id==new.id or run.request.mode!='audit' or run.state not in {'needs_review','paused','failed','interrupted'}:
                    continue
                if new.origin=='mcp' and run.origin!='mcp':
                    continue
                self.event(run.id,'superseded',{'run_id':new.id})
                if run.state=='failed':  # cancel() keeps a failed run as is; a superseded one is closed all the same
                    run.state='cancelled'
                    self._save(run)
                    self.event(run.id,'state',{'state':run.state})
                else:
                    self.cancel(run.id)
            return
        if new.request.mode not in {'stage','edit_loop'} or not new.request.scene_id:
            return
        scene_id=new.request.scene_id
        stage=new.request.stage if new.request.mode=='stage' else 'edit'
        for run in self.list_runs(new.story_id):
            if run.id==new.id or run.state not in {'needs_review','alternative','paused','interrupted'}:
                continue
            # An editor loop waits for its summary with the cursor past its last pass: that pass is its current task.
            remaining=run.tasks[run.cursor:] or run.tasks[-1:]
            # A run that still has other scenes ahead keeps waiting: one manual stage must not drop the automation.
            if not remaining or remaining[0].get('stage')!=stage or any(task.get('scene_id')!=scene_id for task in remaining):
                continue
            self.event(run.id,'superseded',{'run_id':new.id})
            self.cancel(run.id)

    def readiness(self,story_id,scene_id=None,editor_source_head=None,editor_source_version_id=None,operation=None):
        from .readiness import preview
        self.repo.get_story(story_id)
        operations={}
        view=None
        limit=None
        from .edit_pass import resolve_edit_pass_limit
        for name in ([operation] if operation else ['prepare',*STAGES,'scene','remaining','rebuild_memory','edit_loop']):
            # model_construct permits the unselected-scene state in a read-only preview.
            request=RunRequest.model_construct(
                story_id=story_id,
                scene_id=None if name=='audit_story' else scene_id,
                mode='stage' if name in STAGES else 'audit' if name=='audit_story' else name,
                stage=name if name in STAGES else None,
                edit_workflow='loop' if name in {'scene','remaining'} else 'single',
                editor_source_head=editor_source_head if name=='edit_loop' else None,
                editor_source_version_id=editor_source_version_id if name=='edit_loop' else None,
                audit_scope={'audit':'scene','audit_story':'story'}.get(name)
            )
            # One captured view serves every operation of this request.
            if view is None:view=self.repo.context_view(story_id)
            if limit is None:limit=resolve_edit_pass_limit(self.repo,request).edit_pass_limit
            request=request.model_copy(update={'edit_pass_limit':limit})
            operations[name]=preview(self.repo,request,view)
        return {'operations':operations}

    def run_readiness(self,id):
        from .readiness import pending_preview
        return pending_preview(self.repo,self.get_run(id))

    def pause(self, id: str) -> Run:
        with self.condition:
            run=self.get_run(id)
            if run.state not in {'queued','running'}:
                return run
            run.state='pause_requested' if id==self.active_id else 'paused'
            self._save(run)
            self.event(id,'state',{'state':run.state})
            return run

    def cancel(self, id: str) -> Run:
        with self.condition:
            run=self.get_run(id)
            target = CANCEL_TRANSITIONS.get(run.state)
            if run.request.mode == 'memory_carry' and run.state == 'failed':
                target = 'cancelled'  # MEMORY-CARRY: a failed carry keeps later scenes waiting until it is cancelled
            if target is None:
                return run
            run.state = target
            if target == 'cancellation_requested':
                self.cancel_event.set()
            self._save(run)
            self.event(id,'state',{'state':run.state})
            return run

    def cancel_request(self, request: RunRequest, request_id: str) -> Run:
        if not request_id or len(request_id)>200 or request.mode not in {'stage','edit_loop'}:
            raise ValueError('Некоректний запит скасування')
        from .edit_pass import resolve_edit_pass_limit
        with self.condition:
            existing=self.repo.find_run_by_request_id(request_id)
            request=resolve_edit_pass_limit(self.repo,request,existing)  # the same stored request as a later enqueue of this id
            if existing:
                if existing.request!=request:raise RevisionConflict('request_id уже використано для іншого запиту')
                return self.cancel(existing.id)
            candidate=Run(id=new_id(),story_id=request.story_id,request_id=request_id,request=request,tasks=[],state='cancelled',cancelled_before_enqueue=True)
            run,created=self.repo.enqueue_run(candidate)
            if created:self.event(run.id,'state',{'state':'cancelled'})
            return run

    def resume(self, id: str, repeat_interrupted: bool = False) -> Run:
        with self.condition:
            run=self.get_run(id)
            if run.cancelled_before_enqueue:raise ValueError('Скасований до запуску запит не можна відновити')
            if run.request.mode=='impact':raise ValueError(IMPACT_REMOVED)
            if run.state not in TERMINAL-{'completed'}:
                raise ValueError('Запуск ще виконується')
            attempts=self.repo.list_attempts(run.story_id,run.id)
            task=run.tasks[run.cursor] if run.cursor<len(run.tasks) else None
            latest={}
            from .audit_output import AUDIT_STAGES
            for attempt in attempts:
                if (
                    task
                    and (attempt.stage == task['stage'] or task['stage'] == 'audit' and attempt.stage in AUDIT_STAGES)
                    # A book audit task has no scene: its attempts belong to the scenes it checked, one at a time.
                    and (attempt.scene_id == task.get('scene_id') or task['stage'] == 'audit' and task.get('scene_id') is None)
                    and attempt.context.get('run_cursor', run.cursor) == run.cursor
                ):
                    latest[attempt.context.get('checkpoint_key','stage')]=attempt
            uncertain=[a for a in latest.values() if a.state in {'running','interrupted','failed','cancelled'}]
            if run.state in {'failed','interrupted','paused'}:
                from .editor_loop import progress,pipeline,recoverable_failed_pass
                checkpoint=progress(run) if run.request.mode=='edit_loop' or pipeline(run) else None
                if checkpoint and recoverable_failed_pass(self.repo,run):
                    uncertain=[]  # A recorded failure stop authorizes local summary only, never another call.
            if run.state=='cancelled' and any(a.context.get('copyedit_proposal') for a in latest.values()):
                uncertain.append(True)  # Cancellation never authorizes another paid editor call.
            if (
                task
                and task['stage'] == 'evaluate'
                and not latest
                and any(
                    e.type == 'stage_started'
                    and e.data.get('stage') == 'evaluate'
                    and e.data.get('run_cursor', run.cursor) == run.cursor
                    and e.data.get('scene_id', task.get('scene_id')) == task.get('scene_id')
                    for e in self.list_events(id)
                )
            ):
                uncertain.append(True)  # Legacy evaluator runs before persisted attempts also need explicit repeat.
            if uncertain and not repeat_interrupted:
                raise ValueError('Потрібне явне рішення повторити перерваний або невдалий етап')
            result=self.run_readiness(id)
            if not result['ready']:
                raise ValueError(result['reason'])
            from .run_progress import extend_plan,progress_from_events,visited_scene_ids
            try:
                events=self.repo.list_run_events(id,types=PROGRESS_EVENTS)
                progress=progress_from_events(run,events)
                if progress is not None:
                    run.planned_telemetry=extend_plan(run.planned_telemetry,progress,result,visited_scene_ids(events))
            except Exception:  # progress is advisory: a broken computation keeps the plan and never strands the resume
                logging.getLogger(__name__).exception('Не вдалося доповнити план запуску %s',id)
            run.state='queued'
            run.error=None
            self.repo.requeue_run(run)
            self.event(id,'state',{'state':run.state})
            self.condition.notify_all()
            return run

    def continue_after_acceptance(
        self,
        id: str,
        version_id: str,
        expected_cursor: int,
        expected_scene_revision: int,
        acceptance_id: str | None = None,
    ) -> Run:
        from .readiness import pending_preview
        with self.condition:
            run=self.get_run(id)
            if run.state not in {'alternative','needs_review'} or run.cursor!=expected_cursor:
                raise RevisionConflict('Стан або етап запуску змінено')
            next_run=run.model_copy(deep=True)
            next_run.cursor+=1
            if next_run.cursor<len(next_run.tasks):
                result=pending_preview(self.repo,next_run)
                if not result['ready']:
                    raise ValueError(result['reason'])
            current=self.repo.continue_after_acceptance(
                id,
                version_id,
                expected_cursor,
                expected_scene_revision,
                acceptance_id
            )
            self.condition.notify_all()
            return current

    def recover_interrupted(self) -> list[Run]:
        recovered=[]
        with self.condition:
            for run in self.list_runs():
                if run.request.mode=='impact' and run.state not in {'completed','failed','cancelled'}:
                    # R28-REMOVED: nothing can continue an old impact run, and the workspace no longer shows it.
                    run.state='cancelled'
                    run.error=IMPACT_REMOVED
                    self._save(run)
                    self.event(run.id,'state',{'state':run.state})
                    recovered.append(run)
                elif run.request.mode=='memory_carry' and run.state=='cancellation_requested':
                    # MEMORY-CARRY: the author asked to stop it; an interrupted carry would keep its scenes pending.
                    run.state='cancelled'
                    self._save(run)
                    self.event(run.id,'state',{'state':run.state})
                    recovered.append(run)
                elif run.request.mode=='memory_carry' and run.state in {'running','pause_requested','queued'}:
                    # MEMORY-CARRY: a model-free carry has nothing to repeat at a cost; it continues after a restart, so
                    # its scenes stay pending instead of silently diverging (Ruling, R-44 PR 2b Task 3).
                    if run.state!='queued':
                        run.state='queued'
                        self._save(run)
                        self.event(run.id,'state',{'state':run.state})
                    recovered.append(run)
                elif run.state in {'running','cancellation_requested','pause_requested','queued'}:
                    run.state='interrupted'
                    run.error='Попередню сесію перервано. Автоматичного повтору запитів немає.'
                    self._save(run)
                    self.event(run.id,'state',{'state':run.state})
                    recovered.append(run)
            self.repo.recover_running_attempts()
            self.repo.close_accepted_runs()  # RUN-ACCEPT-CLOSE: results accepted before the fix no longer hold runs open
        return recovered

    def start(self) -> None:
        self.lock.__enter__()  # Lock before recovery can touch another process's runs.
        try:
            self.recover_interrupted()
            self.shutdown.clear()
            self.thread=threading.Thread(target=self._loop,name='storygen-worker',daemon=True)
            self.thread.start()
        except BaseException:
            self.lock.__exit__()
            raise

    def stop(self) -> None:
        self.shutdown.set()
        self.cancel_event.set()
        with self.condition:
            self.condition.notify_all()
        if self.thread:
            self.thread.join(timeout=5)

    def _loop(self) -> None:
        try:
            while not self.shutdown.is_set():
                with self.condition:
                    queued=next((r for r in self.list_runs() if r.state=='queued'),None)
                    if queued is None:
                        self.condition.wait(timeout=.5)
                        continue
                    self.active_id=queued.id
                    self.cancel_event.clear()
                    queued.state='running'
                    self._save(queued)
                    self.event(queued.id,'state',{'state':'running'})
                try:
                    # PERF-001: lineage memo for this run only (content-keyed, bounded); never shared with requests.
                    with lineage_scope():
                        self._execute(queued.id)
                except Exception as exc:
                    with self.condition:
                        run=self.get_run(queued.id)
                        run.state='cancelled' if self.cancel_event.is_set() else 'failed'
                        run.error=self._failure_message(run,exc)
                        self._save(run)
                        self.event(run.id,'state',{'state':run.state,'error':run.error})
                finally:
                    with self.condition:
                        self.active_id=None
        finally:
            self.lock.__exit__()

    def _failure_message(self,run,exc):
        from ..providers.policy import ModelPolicyBlocked
        if isinstance(exc,(ContextOverflow,ModelPolicyBlocked)):  # MODEL-003/MODEL-004: the author sees why the call is blocked.
            return str(exc)
        task=run.tasks[run.cursor] if run.cursor<len(run.tasks) else None
        if task and task.get('stage') in {'publication_suggest','timeline_summary'}:
            attempts=self.repo.list_attempts(run.story_id,run.id)
            if attempts:return attempts[-1].error
            return str(exc) if isinstance(exc,ValueError) else 'Технічна помилка пропозиції; автоматичного повтору немає.'
        if not task or task.get('stage')!='evaluate':
            return 'Етап зупинено. Перевірте контекст, конфігурацію й збережені спроби; автоматичного повтору немає.'

        # The evaluator normally converts provider failures into a structured outcome.
        # This path is for unexpected exceptions that escaped that boundary.
        from ..evaluation.failures import safe_message
        from ..providers.secrets import resolve_key

        attempt=None
        try:
            attempts=self.repo.list_attempts(run.story_id,run.id)
            matching=[a for a in attempts if a.stage=='evaluate'
                and a.scene_id==task.get('scene_id')
                and a.context.get('run_cursor',run.cursor)==run.cursor]
            attempt=matching[-1] if matching else None
        except Exception:
            pass
        secret=None
        documents=[]
        try:
            from ..evaluation.story_adapter import get_evaluation_settings
            config=get_evaluation_settings(self.repo,run.story_id).config
            if config.provider in {'openrouter','venice'}:
                secret=resolve_key(config.api_key_env)
        except Exception:
            pass
        if attempt:
            documents=[d['text'] for d in attempt.context.get('case',{}).get('documents',[])
                if isinstance(d,dict) and isinstance(d.get('text'),str)]
        frozen_secret=None
        if attempt:
            frozen_config=attempt.context.get('config',{})
            key_env=frozen_config.get('api_key_env') if isinstance(frozen_config,dict) else None
            if isinstance(key_env,str):
                frozen_secret=resolve_key(key_env)
        diagnostic=safe_message(str(exc),secret,documents,secrets=(frozen_secret,))
        detail=f'{type(exc).__name__}: {diagnostic}' if diagnostic else type(exc).__name__
        message=f'Помилка оцінювача — {detail}. Автоматичного повтору немає.'
        if attempt and attempt.state=='running':
            attempt.state='failed'
            attempt.error=message
            try:
                self.repo.save_attempt(attempt)
            except Exception:
                pass
        return message

    def _execute(self, id: str) -> None:
        if self.get_run(id).request.mode=='impact':
            raise ValueError(IMPACT_REMOVED)
        if self.get_run(id).request.mode=='edit_loop':
            from .editor_loop import execute
            return execute(self,id)
        if self.get_run(id).request.mode=='memory_carry':
            from .memory_carry import execute
            return execute(self,id)
        if self.get_run(id).request.mode=='audit':
            from .audit_run import execute
            return execute(self,id)
        while True:
            with self.condition:
                run=self.get_run(id)
                if self.cancel_event.is_set():
                    run.state='cancelled'
                    self._save(run)
                    self.event(id,'state',{'state':run.state})
                    return
                if run.state=='pause_requested':
                    run.state='paused'
                    self._save(run)
                    self.event(id,'state',{'state':run.state})
                    return
                if run.cursor>=len(run.tasks):
                    run.state='completed'
                    self._save(run)
                    self.event(id,'state',{'state':run.state})
                    return
                task=run.tasks[run.cursor]
            scene_id,stage=task['scene_id'],task['stage']
            if task.get('editor_loop'):
                from .editor_loop import execute
                execute(self,id)
                if self.get_run(id).state=='running':
                    continue
                return
            if stage=='evaluate':
                self._evaluate(run)
                if self.get_run(id).state=='running':
                    continue
                return
            if stage in {'classify','publication_suggest','rewrite','timeline_summary'}:
                if stage=='rewrite':
                    from .assisted_writing import build_rewrite_context
                    context=build_rewrite_context(self.repo,run.request)
                elif stage=='publication_suggest':
                    from .publication_metadata import build_publication_context
                    context=build_publication_context(self.repo,run.story_id,run.request.expected_selection,True)
                elif stage=='timeline_summary':
                    from .timeline_summary import build_summary_context
                    context=build_summary_context(self.repo,run.story_id,run.request.summary_block_key)
                else:
                    from .edit_classification import build_classification_context
                    context=build_classification_context(self.repo,run.request)
                role=context.settings
                self.event(
                    id,
                    'stage_started',
                    {'stage':stage,'scene_id':scene_id,'model':role.provider.model,'provider':role.provider.provider,'estimated_tokens':context.estimated_tokens,'streaming':streams(stage,role,context)}
                )
                attempt=execute_stage(
                    self.repo,
                    scene_id,
                    stage,
                    context,
                    self.gateway_factory(role.provider),
                    self.cancel_event,
                    lambda text:self.event(id,'delta',{'text':text,'stage':stage,'scene_id':scene_id}),
                    id,
                    task_cursor=run.cursor
                )
                with self.condition:
                    current=self.get_run(id)
                    current.state='cancelled' if stage in {'publication_suggest','rewrite','timeline_summary'} and (self.cancel_event.is_set() or current.state in {'cancellation_requested','cancelled'}) else attempt.state
                    current.error=attempt.error
                    warnings=attempt.context.get('publication_warnings',[])+attempt.context.get('broken_text_warnings',[])+attempt.context.get('model_retirement_warnings',[])
                    if warnings:
                        current.warning=merge_warnings(current.warning,warnings)
                        self.event(id,'context_warning',{'warnings':warnings,'stage':stage,'scene_id':None})
                    if attempt.state=='completed':
                        current.cursor+=1
                    self._save(current)
                    self.event(
                        id,
                        'stage_finished',
                        {'attempt_id':attempt.id,'state':attempt.state,'usage':attempt.usage,'finish_reason':attempt.finish_reason}
                    )
                    self.event(id,'state',{'state':current.state,'error':current.error})
                return
            roles=get_role_settings(self.repo,run.story_id)
            if STAGE_ROLES[stage] not in roles:
                raise ValueError('Роль не налаштовано')
            role=roles[STAGE_ROLES[stage]]
            if stage=='prepare':
                view=self.repo.context_view(run.story_id)
                story=view.get_story(run.story_id)
                from .prepare_sources import prepare_sources
                sources=prepare_sources(view,story)
                context=make_context(
                    view,
                    story,
                    None,
                    stage,
                    role,
                    [f'ДЖЕРЕЛО [version_id={v.id}]\n'+view.read_text(v.id) for v in sources],
                    [v.id for v in sources]
                )
            else:
                from ..memory.previous import MergeRequired
                try:
                    context=build_context(self.repo,scene_id,stage,role,memory_approval=run.request.memory_approval if stage=='memory' else None)
                except MergeRequired as exc:
                    # MEMORY-MERGE-S02: stop before the scene, like a core review stop; the author confirms the merge.
                    with self.condition:
                        current=self.get_run(id)
                        current.state='needs_review'
                        current.error=str(exc)
                        self._save(current)
                        self.event(id,'state',{'state':current.state,'error':current.error,'merge_key':exc.merge_key,'scene_id':scene_id})
                    return
                # Reuse only the selected completed stage with exactly matching source/config input.
                scene=self.repo.get_scene(scene_id)
                head={'brief':'brief','draft':'draft','edit':'prose','memory':'memory'}[stage]
                selected=scene.heads.get(head)
                reuse=None
                if run.request.mode!='stage' and selected and not self.repo.get_version(selected).stale:
                    reuse=next(
                        (
                            a for a in reversed(self.repo.list_attempts(run.story_id))
                            if a.result_version_id == selected
                            and a.state == 'completed'
                            and a.context['fingerprint'] == context.fingerprint
                        ),
                        None
                    )
                    if stage=='brief' and not any(a.result_version_id==selected for a in self.repo.list_attempts(run.story_id)):
                        # An explicitly saved/accepted author brief is authoritative until a dependency changes.
                        with self.condition:
                            current=self.get_run(id)
                            current.cursor+=1
                            self._save(current)
                            self.event(
                                id,
                                'reused',
                                {'version_id':selected,'stage':stage,'scene_id':scene_id,'author_version':True}
                            )
                        continue
                if reuse:
                    with self.condition:
                        current=self.get_run(id)
                        current.cursor+=1
                        self._save(current)
                        self.event(id,'reused',{'attempt_id':reuse.id,'stage':stage,'scene_id':scene_id})
                    continue
            if context.context_warnings:
                with self.condition:
                    current=self.get_run(id)
                    current.warning=merge_warnings(current.warning,context.context_warnings)
                    self._save(current)
                    self.event(
                        id,
                        'context_warning',
                        {'warnings':context.context_warnings,'stage':stage,'scene_id':scene_id}
                    )
            self.event(
                id,
                'stage_started',
                {'stage':stage,'scene_id':scene_id,'model':context.settings.provider.model,'provider':context.settings.provider.provider,'estimated_tokens':context.estimated_tokens,'streaming':streams(stage,context.settings,context)}
            )
            attempt=execute_stage(
                self.repo,
                scene_id,
                stage,
                context,
                self.gateway_factory(context.settings.provider),
                self.cancel_event,
                lambda text:self.event(id,'delta',{'text':text,'stage':stage,'scene_id':scene_id}),
                id,
                task_cursor=run.cursor
            )
            with self.condition:
                current=self.get_run(id)
                warnings=attempt.context.get('memory_warnings',[])+attempt.context.get('editor_warnings',[])+attempt.context.get('planner_warnings',[])+attempt.context.get('broken_text_warnings',[])+attempt.context.get('model_retirement_warnings',[])
                if warnings:
                    current.warning=merge_warnings(current.warning,warnings)
                    self._save(current)
                    self.event(id,'context_warning',{'warnings':warnings,'stage':stage,'scene_id':scene_id})
                self.event(
                    id,
                    'stage_finished',
                    {'attempt_id':attempt.id,'state':attempt.state,'usage':attempt.usage,'finish_reason':attempt.finish_reason}
                )
                if attempt.state!='completed':
                    current.state=attempt.state
                    current.error=attempt.error
                    self._save(current)
                    self.event(id,'state',{'state':current.state,'error':current.error})
                    return
                current.cursor+=1
                if self.cancel_event.is_set():
                    current.state='cancellation_requested'
                elif current.state=='pause_requested' or stage in current.request.pause_after:
                    current.state='pause_requested'
                self._save(current)

    def _evaluate(self, run: Run) -> None:
        from ..evaluation.story_adapter import execute_evaluation, get_evaluation_settings
        if get_evaluation_settings(self.repo,run.story_id).policy=='off':
            with self.condition:
                current=self.get_run(run.id)
                current.cursor+=1
                self._save(current)
                self.event(run.id,'evaluation_skipped',{'reason':'Оцінювач вимкнено'})
            return
        task=run.tasks[run.cursor]
        if task.get('evaluation_mode')=='edit_pair':
            from ..evaluation.story_adapter import ENGLISH_NOT_EVALUATED, evaluated_scenes
            view=self.repo.context_view(run.story_id)
            if not evaluated_scenes(view,view.get_story(run.story_id),view.list_scenes(run.story_id),task['scene_id']):
                # STORY-LANGUAGE-S06: automatic evaluation is skipped, not failed, when the scene became English after queueing.
                with self.condition:
                    current=self.get_run(run.id)
                    current.cursor+=1
                    self._save(current)
                    self.event(run.id,'evaluation_skipped',{'scene_id':task['scene_id'],'reason':ENGLISH_NOT_EVALUATED})
                return
        execute_evaluation(self,run)
