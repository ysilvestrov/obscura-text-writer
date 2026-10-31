"""Sequential protocol2 executor: every leaf and synthesis has durable proof."""
from ..domain import RevisionConflict
from ..impact.chunk_validation import validate_manifest,verify_attempt,closure,combined_result
from ..impact.models import ImpactRecord,TEXT_STAMP_EXCLUDE
from ..impact.planning import capture_target
from .impact_chunk_context import build_chunk_context


def reusable(repo,run,manifest,task,results):
    matches=[a for a in repo.list_attempts(run.story_id,run.id) if a.stage=='impact_part' and a.context.get('impact_chunk_manifest')==manifest.fingerprint and a.context.get('impact_chunk_task')==task]
    completed=[a for a in matches if a.state=='completed' and a.finish_reason=='stop']
    if completed:
        attempt=completed[-1]
        verify_attempt(attempt,manifest,task,results,repo.files.read_partial,run.story_id,run.id)
        return attempt
    from ..impact.result_budget import REVISION,budget_size,compact_size,recoverable_failure
    failed=[a for a in matches if manifest.wire_schema_version==2 and recoverable_failure(a)]
    if not failed:return None
    attempt=failed[-1]
    from ..impact.validation import decode_response
    from ..impact.chunk_validation import validate_part
    from ..domain import now
    try:result=validate_part(decode_response(repo.files.read_partial(attempt.partial_path)),manifest,task,results)
    except ValueError:return None  # Keep the existing explicit-repeat gate for genuinely invalid output.
    # Never rewrite raw output or bypass owner/body/source/evidence gates.
    repaired=attempt.model_copy(deep=True)
    repaired.context.setdefault('validation_history',[]).append(dict(revision=REVISION,at=now(),previous_state=attempt.state,previous_error=attempt.error,previous_failure=attempt.context.get('impact_failure'),model_call=False,
        canonical_chars=compact_size(result.model_dump()),model_data_chars=budget_size(result.model_dump(),2)))
    repaired.context.pop('impact_failure',None)
    repaired.context['impact_result']=result.model_dump()
    repaired.state='completed';repaired.error=None
    verify_attempt(repaired,manifest,task,results,repo.files.read_partial,run.story_id,run.id)
    return repo.save_attempt(repaired)


def load_results(repo,run,manifest):
    expected=manifest.tasks[:run.cursor]
    if set(run.impact['proofs'])!={t['id'] for t in expected}:raise ValueError('Checkpoint має неповний набір частин')
    results={}
    for task in expected:
        attempt=repo.get_attempt(run.impact['proofs'][task['id']])
        result=verify_attempt(attempt,manifest,task,results,repo.files.read_partial,run.story_id,run.id)
        results[task['id']]=result.model_dump()
    return results


def advance(worker,run,manifest,task,attempt):
    with worker.condition:
        current=worker.get_run(run.id)
        if worker.cancel_event.is_set() or current.state in {'cancelled','cancellation_requested'}:
            current.state='cancelled';worker._save(current);return
        current.impact['proofs'][task['id']]=attempt.id
        # Publish only at a complete material root, after all memory checks if present.
        for version,roots in manifest.roots.items():
            final=roots['memory'] or roots['text']
            if task['id']!=final:continue
            target=next(t for t in manifest.plan.targets if t.version_id==version)
            live=capture_target(worker.repo.context_view(run.story_id),version)
            if live.model_dump(exclude=TEXT_STAMP_EXCLUDE|{'baseline_ids'})!=target.model_dump(exclude=TEXT_STAMP_EXCLUDE|{'baseline_ids'}):raise RevisionConflict('Передумови або цільовий текст змінилися; частини не застосовано')
            view=worker.repo.context_view(run.story_id)
            changed={k for k in set(live.baseline_ids)|set(target.baseline_ids) if live.baseline_ids.get(k)!=target.baseline_ids.get(k)}
            own={'impact:'+r.id for r in view.impact_records.values() if r.run_id==run.id and r.verdict.verdict=='no_impact'}
            if any(live.baseline_ids.get(k) not in own for k in changed):raise RevisionConflict('Зовнішня зміна бази перевірки; частини не застосовано')
            results={id:worker.repo.get_attempt(a).context['impact_result'] for id,a in current.impact['proofs'].items()}
            target=target.model_copy(update={'baseline_ids':live.baseline_ids,'fingerprint':live.fingerprint})
            verdict,memory,explanation=combined_result(manifest,target,results)
            required=closure(manifest,[roots['text'],roots['memory']])
            proof_ids={t['id']:current.impact['proofs'][t['id']] for t in required}
            root_attempt=worker.repo.get_attempt(proof_ids[roots['text']])
            record=ImpactRecord(schema_version=2,id=root_attempt.id,story_id=run.story_id,run_id=run.id,attempt_id=root_attempt.id,target=target,
                delta_attempt_id=proof_ids[roots['delta']],verdict=verdict,memory_semantic_impact=memory,memory_explanation=explanation,
                chunk_manifest=manifest.model_dump(),proof_attempt_ids=proof_ids,created_at=root_attempt.created_at)
            worker.repo.impact('save_report',record=record)
            worker.event(run.id,'impact_result',{'record_id':record.id,'scene_id':target.scene_id,'material':target.material,'verdict':verdict.verdict})
        current.cursor+=1
        current.state='paused' if current.state in {'pause_requested','paused'} else 'completed' if current.cursor==len(current.tasks) else 'running'
        current.error=None;worker._save(current);worker.event(run.id,'state',{'state':current.state})


def execute(worker,id):
    from .stages import execute_stage
    from pydantic import ValidationError
    try:
        manifest=validate_manifest(worker.get_run(id).impact['manifest'])
        while True:
            with worker.condition:
                run=worker.get_run(id)
                if worker.cancel_event.is_set() or run.state in {'cancelled','cancellation_requested'}:
                    run.state='cancelled';worker._save(run);worker.event(id,'state',{'state':run.state});return
                if run.state in {'pause_requested','paused'}:
                    run.state='paused';worker._save(run);worker.event(id,'state',{'state':run.state});return
                if run.cursor>=len(run.tasks):
                    run.state='completed';worker._save(run);worker.event(id,'state',{'state':run.state});return
                if run.tasks!=manifest.tasks:raise ValueError('Черга не відповідає маніфесту частин')
                run.state='running';worker._save(run)
            task=run.tasks[run.cursor];target=next(t for t in manifest.plan.targets if t.version_id==task['version_id'])
            live=capture_target(worker.repo.context_view(run.story_id),target.version_id)
            if live.model_dump(exclude=TEXT_STAMP_EXCLUDE|{'baseline_ids'})!=target.model_dump(exclude=TEXT_STAMP_EXCLUDE|{'baseline_ids'}) or worker.repo.get_scene(target.scene_id).heads.get(target.material)!=target.version_id:raise RevisionConflict('Передумови або цільовий текст змінилися; частини не застосовано')
            results=load_results(worker.repo,run,manifest)
            attempt=reusable(worker.repo,run,manifest,task,results)
            if attempt is None:
                context=build_chunk_context(worker.repo,manifest,task,results)
                if context.settings.provider.provider in {'venice','openrouter'} and run.request.budget_limit_usd is None:raise ValueError('Потрібен явний ліміт бюджету перевірки впливу')
                with worker.condition:
                    current=worker.get_run(id)
                    if worker.cancel_event.is_set() or current.state in {'paused','pause_requested','cancelled','cancellation_requested'}:continue
                worker.event(id,'stage_started',{'stage':'impact_part','phase':task['phase'],'part':run.cursor+1,'parts':len(run.tasks),'scene_id':task['scene_id'],'model':context.settings.provider.model,'provider':context.settings.provider.provider,'estimated_tokens':context.estimated_tokens})
                attempt=execute_stage(worker.repo,task['scene_id'],'impact_part',context,worker.gateway_factory(context.settings.provider),worker.cancel_event,
                    lambda text:worker.event(id,'delta',{'text':text,'stage':'impact_part','scene_id':task['scene_id']}),id,task_cursor=run.cursor)
                worker.event(id,'stage_finished',{'attempt_id':attempt.id,'state':attempt.state,'usage':attempt.usage,'finish_reason':attempt.finish_reason})
            if attempt.state!='completed':
                current=worker.get_run(id);current.state='cancelled' if worker.cancel_event.is_set() else 'failed';current.error=attempt.error;worker._save(current);worker.event(id,'state',{'state':current.state,'error':current.error});return
            advance(worker,run,manifest,task,attempt)
            if worker.get_run(id).state!='running':return
    except Exception as exc:
        with worker.condition:
            current=worker.get_run(id)
            current.state='cancelled' if worker.cancel_event.is_set() or current.state in {'cancelled','cancellation_requested'} else 'alternative' if isinstance(exc,RevisionConflict) else 'failed'
            current.error=str(exc) if isinstance(exc,ValueError) and not isinstance(exc,ValidationError) else 'Не вдалося завершити перевірку частинами; успішні частини збережено. Автоматичного повтору немає.'
            worker._save(current);worker.event(id,'state',{'state':current.state,'error':current.error})
