"""One scene at a time, with durable search and memory checkpoints."""
from ..domain import RevisionConflict
from ..impact.models import ImpactTarget
from .capture import capture
from ..authoring.blueprints import get_role_settings
from .planning import prepare_scene,check_specs,synthesis_spec,stamp
from .proofs import verify_part,verify_report
from .models import SceneReport
from .store import publish_scene,save_report


def resume(worker,run,repeat):
    if any(r.id!=run.id and r.impact and r.impact.get('protocol')==3 and r.state in {'queued','running','paused','needs_review','pause_requested','cancellation_requested'} for r in worker.list_runs(run.story_id)):raise ValueError('Інший перегляд книги вже відкрито')
    if run.state not in {'failed','interrupted','paused','cancelled'}:raise ValueError('Спершу завершіть авторський перегляд зауважень')
    if run.impact.get('phase') in {'awaiting_author','author_editing'}:raise ValueError('Потрібне авторське рішення у панелі перевірки книги')
    latest={}
    for a in worker.repo.list_attempts(run.story_id,run.id):
        if a.stage not in {'memory','review_part'} or a.context.get('run_cursor')!=run.cursor:continue
        if a.stage=='review_part' and a.context.get('review_plan_id')!=run.impact.get('scene_plan',{}).get('id'):continue
        spec=a.context.get('review_spec',{})
        geometry=tuple((key,str(spec.get(key))) for key in ['phase','source_refs','target_refs','dependencies','rule_ids'])
        latest[(a.stage,a.scene_id,geometry)]=a
    uncertain=any(a.state in {'failed','running','interrupted','cancelled'} for a in latest.values())
    if (run.impact.get('failed_attempt') or uncertain or run.state=='cancelled') and not repeat:raise ValueError('Потрібне явне рішення повторити невдалий або перерваний етап')
    from .readiness import readiness
    ready=readiness(worker.repo,run.request,run)
    if not ready['ready']:raise ValueError(ready['reason'])
    run.impact.pop('failed_attempt',None);run.state='queued';run.error=None
    worker.repo.requeue_run(run);worker.event(run.id,'state',{'state':run.state})
    return run


def live_plan(repo,plan):
    view=repo.context_view(plan['story_id'])
    for raw in plan['targets']:
        t=ImpactTarget.model_validate(raw)
        mode=plan.get('basis_modes',{}).get(t.version_id,'historical_delta')
        if view.get_scene(t.scene_id).heads.get(t.material)!=t.version_id or capture(view,t.version_id,mode).fingerprint!=t.fingerprint:
            raise RevisionConflict('Передумови або текст поточної сцени змінилися; створіть нову перевірку')


def results_for(repo,run):
    results={};data=run.impact
    for id in data['order']:
        results[id]=verify_part(repo.get_attempt(data['proofs'][id]),data['scene_plan'],data['specs'][id],results,repo.files.read_partial,run.story_id,run.id)
    return results


def call(worker,run,stage,context):
    from ..generation.stages import execute_stage
    if context.settings.provider.provider in {'venice','openrouter'} and run.request.budget_limit_usd is None:raise ValueError('Потрібен явний ліміт бюджету перевірки')
    worker.event(run.id,'stage_started',dict(stage=stage,scene_id=context.scene_id,phase=run.impact['phase'],model=context.settings.provider.model,provider=context.settings.provider.provider,estimated_tokens=context.estimated_tokens))
    a=execute_stage(worker.repo,context.scene_id,stage,context,worker.gateway_factory(context.settings.provider),worker.cancel_event,
        lambda text:worker.event(run.id,'delta',dict(stage=stage,scene_id=context.scene_id,text=text)),run.id,task_cursor=run.cursor)
    worker.event(run.id,'stage_finished',dict(attempt_id=a.id,state=a.state,usage=a.usage,finish_reason=a.finish_reason))
    if a.state!='completed':
        current=worker.get_run(run.id);current.impact['failed_attempt']=a.id
        current.state='cancelled' if worker.cancel_event.is_set() else 'failed';current.error=a.error or 'Етап не завершено';worker._save(current)
        worker.event(run.id,'state',dict(state=current.state));return None
    return a


def memory_next(repo,run,through):
    """Only the chronological current prefix; no implicit historical consent."""
    from ..memory.journal import load_memory
    from ..memory.service import validate_memory
    scenes=repo.list_scenes(run.story_id);sources={}
    for scene in scenes[:through+1]:
        prose=scene.heads.get('prose')
        if not prose:continue
        sources[prose]=repo.read_text(prose);memory=scene.heads.get('memory')
        if memory:
            try:
                ref=repo.get_version(memory)
                if not ref.complete or ref.stale:raise ValueError('Застаріла пам’ять')
                validate_memory(load_memory(repo.read_text(memory)),sources)
                continue
            except (ValueError,OSError):
                # A rebuild is not permission to erase author-maintained material.
                try:old=load_memory(repo.read_text(memory))
                except (ValueError,OSError) as exc:raise ValueError('Некоректна попередня пам’ять; виправте її вручну перед продовженням') from exc
                from ..memory.journal import MemoryJournal
                entries=old.events if isinstance(old,MemoryJournal) else [entry for field in ['facts','character_states','open_threads','timeline'] for entry in getattr(old,field)]
                own=[entry for entry in entries if repo.get_version(entry.source_version_id).scene_id==scene.id]
                generated=any(a.stage=='memory' and a.result_version_id==memory and a.state=='completed' for a in repo.list_attempts(run.story_id))
                owned_ids={entry.claim_id for entry in own if hasattr(entry,'claim_id')}
                choices={key for item in scenes for key in item.memory_forwarding}
                if own and (not generated or owned_ids&choices):
                    raise ValueError('Пам’ять сцени «'+scene.title+'» містить авторські записи або вибір «передавати далі», які автоматична перебудова може втратити. Оновіть пам’ять цієї сцени вручну зі збереженням потрібних записів, потім відновіть перегляд.')
        from ..generation.context import build_context
        return build_context(repo,scene.id,'memory',get_role_settings(repo,run.story_id)['memory'])
    return None


def next_search(repo,run,results):
    d=run.impact;plan=d['scene_plan']
    attempts=repo.list_attempts(run.story_id,run.id)
    def pinned(spec):
        shape=lambda s:{k:v for k,v in s.items() if k not in {'id','settings'}}
        saved=next((s for s in d['specs'].values() if shape(s)==shape(spec)),None)
        if saved:return saved
        saved=next((a.context['review_spec'] for a in reversed(attempts) if a.stage=='review_part' and a.state=='completed' and a.finish_reason=='stop' and a.context.get('review_plan_id')==plan['id'] and shape(a.context.get('review_spec',{}))==shape(spec)),None)
        if saved:return saved  # Answer persisted before checkpoint/settings change.
        spec={**spec,'settings':get_role_settings(repo,run.story_id)['planner'].model_dump()}
        spec['id']=stamp(spec)
        return spec
    for spec in plan['delta_specs']:
        spec=pinned(spec)
        if spec['id'] not in results:return spec
    checks=[pinned(s) for s in check_specs(repo,plan,results)]
    for spec in checks:
        if spec['id'] not in results:return spec
    ids=[s['id'] for s in checks];force=True
    while len(ids)>1 or force:
        next_ids=[]
        for start in range(0,len(ids),2):
            spec=pinned(synthesis_spec(repo,plan,ids[start:start+2],results))
            if spec['id'] not in results:return spec
            next_ids.append(spec['id'])
        ids=next_ids;force=False
    d['roots']=ids
    return None


def execute(worker,id):
    from .context import build
    repo=worker.repo
    try:
        while True:
            run=worker.get_run(id);d=run.impact;scenes=repo.list_scenes(run.story_id)
            if worker.cancel_event.is_set() or run.state in {'cancelled','cancellation_requested'}:
                run.state='cancelled';worker._save(run);return
            if run.state in {'pause_requested','paused'}:
                run.state='paused';worker._save(run);return
            if run.state in {'needs_review','failed','completed'}:return
            if [s.id for s in scenes]!=d['scene_order']:raise RevisionConflict('Порядок сцен змінився; створіть нову перевірку')
            if d['scene_cursor']>=len(scenes):
                run.state='completed';worker._save(run);worker.event(id,'state',dict(state=run.state));return
            run.state='running';worker._save(run);cursor=d['scene_cursor'];scene=scenes[cursor]
            if d['phase'] in {'prepare','memory_refresh'}:
                if d['phase']=='memory_refresh' and d.get('acceptance_operation'):
                    from .store import current_acceptance
                    view=repo.context_view(run.story_id)
                    operation=view.review_operations[d['acceptance_operation']]
                    if any(not current_acceptance(view,a['target']['version_id']) for a in operation['result']['acceptances']):
                        raise RevisionConflict('Матеріали змінилися після прийняття сцени; створіть нову перевірку')
                context=memory_next(repo,run,cursor-1 if d['phase']=='prepare' else cursor)
                if context:
                    a=call(worker,run,'memory',context)
                    if a is None:return
                    continue  # Re-read committed heads. Crash here reuses the current journal.
                if d['phase']=='memory_refresh':
                    d.update(scene_cursor=cursor+1,phase='prepare',pending_memory=False)
                    for key in ['scene_plan','current_report_id','acceptance_operation']:d.pop(key,None)
                    d.update(proofs={},specs={},order=[],roots=[]);run.cursor=cursor+1;worker._save(run)
                    worker.event(id,'state',dict(state=run.state,scene_cursor=d['scene_cursor'],parts=0));continue
                plan=prepare_scene(repo,scene.id)
                if not plan['targets']:
                    d['phase']='memory_refresh';worker._save(run);continue
                d.update(scene_plan=plan,phase='search',proofs={},specs={},order=[],roots=[]);worker._save(run);continue
            if d['phase']!='search':raise ValueError('Невідомий стан послідовного перегляду')
            plan=d['scene_plan'];live_plan(repo,plan);results=results_for(repo,run);spec=next_search(repo,run,results)
            if spec:
                matches=[a for a in repo.list_attempts(run.story_id,run.id) if a.stage=='review_part' and a.context.get('review_plan_id')==plan['id'] and a.context.get('review_spec')==spec and a.state=='completed']
                if matches:
                    a=matches[-1];verify_part(a,plan,spec,results,repo.files.read_partial,run.story_id,run.id)
                else:
                    a=call(worker,run,'review_part',build(repo,plan,spec,results))
                    if a is None:return
                current=worker.get_run(id)
                if current.state in {'cancelled','cancellation_requested'}:continue
                current.impact['proofs'][spec['id']]=a.id;current.impact['specs'][spec['id']]=spec;current.impact['order'].append(spec['id']);worker._save(current)
                worker.event(id,'state',dict(state=current.state,scene_cursor=current.impact['scene_cursor'],parts=len(current.impact['order'])));continue
            concerns={c['id']:c for result in results.values() for c in result['concerns']}
            report=SceneReport(story_id=run.story_id,scene_id=scene.id,run_id=run.id,targets=plan['targets'],complete=True,concerns=list(concerns.values()),
                registry=plan['registry'],part_specs=d['specs'],proofs=d['proofs'],coverage=dict(plan=plan,order=d['order'],roots=d['roots']))
            verify_report(report,{a.id:a for a in repo.list_attempts(run.story_id,run.id)},repo.files.read_partial)
            if report.concerns:
                save_report(repo,run,report);worker.event(id,'state',dict(state='needs_review'));return
            publish_scene(repo,id,report,'model_no_concerns','auto-'+plan['id'])
            worker.event(id,'scene_reviewed',dict(scene_id=scene.id,authority='model_no_concerns'))
    except (ValueError,KeyError,OSError) as exc:
        run=worker.get_run(id);run.state='alternative' if isinstance(exc,RevisionConflict) else 'failed';run.error=str(exc);worker._save(run);worker.event(id,'state',dict(state=run.state))
