"""Sequential delta/check queue with durable proof reuse and guarded publication."""
from ..domain import RevisionConflict
from ..impact.models import ImpactPlan,ImpactRecord,TEXT_STAMP_EXCLUDE
from ..impact.planning import capture_target
from .impact_context import build_impact_context,reusable_attempt


def advance(worker,run,attempt):
    with worker.condition:
        current=worker.get_run(run.id)
        if worker.cancel_event.is_set() or current.state in {'cancelled','cancellation_requested'}:
            current.state='cancelled';worker._save(current);return
        task=current.tasks[current.cursor]
        if task['stage']=='impact_delta':
            current.impact['deltas'][task['group_id']]=attempt.id
        else:
            from ..impact.models import ImpactTarget,CheckReport
            target=ImpactTarget.model_validate(attempt.context['impact_target'])
            result=CheckReport.model_validate(attempt.context['impact_result'])
            record=ImpactRecord(id=attempt.id,story_id=current.story_id,run_id=current.id,attempt_id=attempt.id,target=target,
                delta_attempt_id=current.impact['deltas'][task['group_id']],verdict=result.materials[0],
                memory_semantic_impact=result.memory_semantic_impact,memory_explanation=result.memory_explanation,created_at=attempt.created_at)
            worker.repo.impact('save_report',record=record)
            worker.event(run.id,'impact_result',{'record_id':record.id,'scene_id':target.scene_id,'material':target.material,'verdict':record.verdict.verdict})
        current.cursor+=1
        current.state='paused' if current.state in {'pause_requested','paused'} else 'completed' if current.cursor==len(current.tasks) else 'running'
        current.error=None;worker._save(current)
        worker.event(run.id,'state',{'state':current.state})


def execute(worker,id):
    from .stages import execute_stage
    from pydantic import ValidationError
    try:
        while True:
            with worker.condition:
                run=worker.get_run(id)
                if worker.cancel_event.is_set() or run.state in {'cancelled','cancellation_requested'}:
                    run.state='cancelled';worker._save(run);worker.event(id,'state',{'state':run.state});return
                if run.state in {'pause_requested','paused'}:
                    run.state='paused';worker._save(run);worker.event(id,'state',{'state':run.state});return
                if run.cursor>=len(run.tasks):
                    run.state='completed';worker._save(run);worker.event(id,'state',{'state':run.state});return
                run.state='running';worker._save(run)
            task=run.tasks[run.cursor];plan=ImpactPlan.model_validate(run.impact['plan'])
            target=next(t for t in plan.targets if t.version_id==task['version_id'])
            live=capture_target(worker.repo.context_view(run.story_id),target.version_id)
            scene=worker.repo.get_scene(target.scene_id)
            if live.fingerprint!=target.fingerprint:
                # Only this run's already published positive source assessments may advance the review basis.
                keys=set(live.baseline_ids)|set(target.baseline_ids)
                changed=[k for k in keys if live.baseline_ids.get(k)!=target.baseline_ids.get(k)]
                own={r.id for r in worker.repo.context_view(run.story_id).impact_records.values() if r.run_id==id and r.verdict.verdict=='no_impact'}
                allowed=changed and all(live.baseline_ids.get(k) in {'impact:'+r for r in own} for k in changed)
                left=live.model_dump(exclude=TEXT_STAMP_EXCLUDE|{'baseline_ids'})
                right=target.model_dump(exclude=TEXT_STAMP_EXCLUDE|{'baseline_ids'})
                if allowed and left==right:
                    target=live
                    with worker.condition:
                        current=worker.get_run(id)
                        current.impact['plan']['targets']=[target.model_dump() if t['version_id']==target.version_id else t for t in current.impact['plan']['targets']]
                        worker._save(current);run=current
            if live.fingerprint!=target.fingerprint or scene.heads.get(target.material)!=target.version_id:
                raise RevisionConflict('Передумови або цільовий текст змінилися; перевірку не застосовано')
            attempt=reusable_attempt(worker.repo,run,task,target)
            if attempt is None:
                delta=None
                if task['stage']=='impact_check':
                    d=worker.repo.get_attempt(run.impact['deltas'][task['group_id']])
                    delta=d.context['impact_result']
                    if delta.get('uncertainty'):raise ValueError('Дельта неповна: '+delta['uncertainty'])
                context=build_impact_context(worker.repo,target,task['stage'],delta)
                if context.settings.provider.provider in {'venice','openrouter'} and run.request.budget_limit_usd is None:
                    raise ValueError('Потрібен явний ліміт бюджету перевірки впливу')
                with worker.condition:
                    latest=worker.get_run(id)
                    if latest.state in {'paused','pause_requested','cancelled','cancellation_requested'} or worker.cancel_event.is_set():
                        latest.state='cancelled' if latest.state in {'cancelled','cancellation_requested'} or worker.cancel_event.is_set() else 'paused'
                        worker._save(latest);worker.event(id,'state',{'state':latest.state});return
                if context.context_warnings:
                    from ..run_models import merge_warnings
                    with worker.condition:
                        latest=worker.get_run(id);latest.warning=merge_warnings(latest.warning,context.context_warnings);worker._save(latest)
                    worker.event(id,'context_warning',{'warnings':context.context_warnings,'stage':task['stage'],'scene_id':target.scene_id})
                worker.event(id,'stage_started',{'stage':task['stage'],'scene_id':target.scene_id,'model':context.settings.provider.model,'provider':context.settings.provider.provider,'estimated_tokens':context.estimated_tokens})
                attempt=execute_stage(worker.repo,target.scene_id,task['stage'],context,worker.gateway_factory(context.settings.provider),worker.cancel_event,
                    lambda text:worker.event(id,'delta',{'text':text,'stage':task['stage'],'scene_id':target.scene_id}),id,task_cursor=run.cursor)
                worker.event(id,'stage_finished',{'attempt_id':attempt.id,'state':attempt.state,'usage':attempt.usage,'finish_reason':attempt.finish_reason})
            if attempt.state!='completed':
                current=worker.get_run(id);current.state='cancelled' if worker.cancel_event.is_set() else 'failed';current.error=attempt.error
                worker._save(current);worker.event(id,'state',{'state':current.state,'error':current.error});return
            advance(worker,run,attempt)
            if worker.get_run(id).state!='running':return
    except Exception as exc:
        with worker.condition:
            current=worker.get_run(id)
            current.state='cancelled' if worker.cancel_event.is_set() or current.state in {'cancelled','cancellation_requested'} else 'alternative' if isinstance(exc,RevisionConflict) else 'failed'
            current.error=(str(exc) if isinstance(exc,ValueError) and not isinstance(exc,ValidationError) else 'Не вдалося завершити перевірку впливу; збережені спроби доступні. Автоматичного повтору немає.')
            worker._save(current);worker.event(id,'state',{'state':current.state,'error':current.error})
