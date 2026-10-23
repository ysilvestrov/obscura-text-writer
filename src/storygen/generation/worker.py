import threading


from ..authoring.blueprints import get_role_settings
from ..domain import RevisionConflict, new_id
from ..storage.locking import AppInstanceLock
from ..providers.streaming import build_generation_gateway
from .context import build_context, make_context, ContextOverflow
from ..run_models import Run, RunRequest, RunEvent, merge_warnings
from .pipeline import STAGES, STAGE_ROLES
from .stages import execute_stage


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
        return self.repo.append_run_event(id,type,data)

    def list_events(self,id,after_seq=0):
        return self.repo.list_run_events(id,after_seq)

    def enqueue(self,request: RunRequest,request_id: str) -> Run:
        if not request_id or len(request_id)>200:
            raise ValueError('Потрібен request_id до 200 символів')
        existing=self.repo.find_run_by_request_id(request_id)
        if existing:
            if existing.request!=request:
                raise RevisionConflict('request_id уже використано для іншого запиту')
            return existing
        self.repo.get_story(request.story_id)
        scenes=self.repo.list_scenes(request.story_id)
        if request.scene_id and request.scene_id not in {s.id for s in scenes}:
            raise ValueError('Сцена не належить цьому твору')
        if request.mode=='publication_suggest':
            tasks=[{'scene_id':None,'stage':'publication_suggest'}]
        elif request.mode=='prepare':
            tasks=[{'scene_id':None,'stage':'prepare'}]
        elif request.mode=='evaluate':
            tasks=[{'scene_id':request.scene_id,'stage':'evaluate'}]
        elif request.mode=='edit_loop':
            tasks=[{'scene_id':request.scene_id,'stage':'edit'} for _ in range(request.edit_pass_limit)]
        elif request.mode=='classify':
            tasks=[{'scene_id':request.scene_id,'stage':'classify'}]
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
                    expanded=[]
                    for task in tasks:
                        expanded.append(task)
                        if task['stage']=='memory':
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
            candidate=Run(id=new_id(),story_id=request.story_id,request_id=request_id,request=request,tasks=tasks)
            run,created=self.repo.enqueue_run(candidate)
            if created:
                self.event(run.id,'state',{'state':'queued'})
            self.condition.notify_all()
        return run

    def readiness(self,story_id,scene_id=None):
        from .readiness import preview
        self.repo.get_story(story_id)
        operations={}
        for name in ['prepare',*STAGES,'scene','remaining','rebuild_memory','edit_loop']:
            # model_construct permits the unselected-scene state in a read-only preview.
            request=RunRequest.model_construct(
                story_id=story_id,
                scene_id=scene_id,
                mode='stage' if name in STAGES else name,
                stage=name if name in STAGES else None,
                edit_workflow='loop' if name in {'scene','remaining'} else 'single'
            )
            operations[name]=preview(self.repo,request)
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
            if target is None:
                return run
            run.state = target
            if target == 'cancellation_requested':
                self.cancel_event.set()
            self._save(run)
            self.event(id,'state',{'state':run.state})
            return run

    def resume(self, id: str, repeat_interrupted: bool = False) -> Run:
        with self.condition:
            run=self.get_run(id)
            if run.state not in TERMINAL-{'completed'}:
                raise ValueError('Запуск ще виконується')
            attempts=self.repo.list_attempts(run.story_id,run.id)
            task=run.tasks[run.cursor] if run.cursor<len(run.tasks) else None
            latest={}
            for attempt in attempts:
                if (
                    task
                    and attempt.stage == task['stage']
                    and attempt.scene_id == task.get('scene_id')
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
                if run.state in {'running','cancellation_requested','pause_requested','queued'}:
                    run.state='interrupted'
                    run.error='Попередню сесію перервано. Автоматичного повтору запитів немає.'
                    self._save(run)
                    self.event(run.id,'state',{'state':run.state})
                    recovered.append(run)
            self.repo.recover_running_attempts()
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
        if isinstance(exc,ContextOverflow):
            return str(exc)
        task=run.tasks[run.cursor] if run.cursor<len(run.tasks) else None
        if task and task.get('stage')=='publication_suggest':
            attempts=self.repo.list_attempts(run.story_id,run.id)
            if attempts:return attempts[-1].error
            return str(exc) if isinstance(exc,ValueError) else 'Технічна помилка пропозиції; автоматичного повтору немає.'
        if not task or task.get('stage')!='evaluate':
            return 'Етап зупинено. Перевірте контекст, конфігурацію й збережені спроби; автоматичного повтору немає.'

        # The evaluator normally converts provider failures into a structured outcome.
        # This path is for unexpected exceptions that escaped that boundary.
        from ..evaluation.failures import safe_message
        import os

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
                secret=os.environ.get(config.api_key_env)
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
                frozen_secret=os.environ.get(key_env)
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
        if self.get_run(id).request.mode=='edit_loop':
            from .editor_loop import execute
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
            if stage in {'classify','publication_suggest'}:
                if stage=='publication_suggest':
                    from .publication_metadata import build_publication_context
                    context=build_publication_context(self.repo,run.story_id)
                else:
                    from .edit_classification import build_classification_context
                    context=build_classification_context(self.repo,run.request)
                role=context.settings
                self.event(
                    id,
                    'stage_started',
                    {'stage':stage,'scene_id':scene_id,'model':role.provider.model,'provider':role.provider.provider,'estimated_tokens':context.estimated_tokens}
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
                    current.state='cancelled' if stage=='publication_suggest' and (self.cancel_event.is_set() or current.state in {'cancellation_requested','cancelled'}) else attempt.state
                    current.error=attempt.error
                    warnings=attempt.context.get('publication_warnings',[])
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
                sources = [
                    s for s in [
                        view.active_source(story.id, 'source_plan'),
                        view.active_source(story.id, 'source_characters'),
                    ] if s
                ]
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
                context=build_context(self.repo,scene_id,stage,role)
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
                {'stage':stage,'scene_id':scene_id,'model':role.provider.model,'provider':role.provider.provider,'estimated_tokens':context.estimated_tokens}
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
                warnings=attempt.context.get('memory_warnings',[])+attempt.context.get('editor_warnings',[])+attempt.context.get('planner_warnings',[])
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
        execute_evaluation(self,run)
