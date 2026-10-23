"""Bounded editor passes on immutable working copies, with one final review."""
from ..authoring.blueprints import get_role_settings
from ..domain import StageAttempt,new_id
from ..dependency_models import TargetCAS
from ..storage.snapshots import compare_snapshot
from .context import make_context,ContextBundle,ContextOverflow


def pipeline(run):
    return run.request.mode in {'scene','remaining'} and run.cursor<len(run.tasks) and bool(run.tasks[run.cursor].get('editor_loop'))


def progress(run):
    return run.editor_loops.get(str(run.cursor)) if pipeline(run) else run.editor_loop


def scene_id(run):
    return run.tasks[run.cursor]['scene_id'] if pipeline(run) else run.request.scene_id


def pass_index(run):
    return progress(run).get('pass_cursor',0) if pipeline(run) else run.cursor


def task_key(run):
    return str(run.cursor) if pipeline(run) else ''


def completed_pass(attempt,run):
    return attempt.state=='completed' and (attempt.context.get('fragments',{}).get('edit_loop_pass_index')==str(pass_index(run)) if pipeline(run) else attempt.context.get('run_cursor')==run.cursor)


def recoverable_failed_pass(repo,run):
    data=progress(run)
    if not data or data['current_version_id']==data['base_version_id']:return None
    for attempt in reversed(model_attempts(repo,run)):
        matching=(attempt.context.get('fragments',{}).get('edit_loop_pass_index')==str(pass_index(run)) if pipeline(run) else attempt.context.get('run_cursor')==run.cursor)
        if matching:
            return attempt if attempt.state=='failed' and attempt.context.get('edit_loop_failure_origin')=='model_response' else None
    return None


def source(repo,scene_id,prefer_draft=False):
    scene=repo.get_scene(scene_id)
    id=scene.heads.get('draft') if prefer_draft else scene.heads.get('prose') or scene.heads.get('draft')
    if not id:raise ValueError('Спершу створіть прозу або чернетку')
    ref=repo.get_version(id)
    if ref.stale or not ref.complete or not repo.read_text(id).strip():
        raise ValueError('Вибрана проза або чернетка потребує оновлення')
    return scene,ref


def role(repo,story_id):
    settings=get_role_settings(repo,story_id).get('editor')
    if not settings:raise ValueError('Роль не налаштовано: editor')
    return settings


def context(repo,scene_id,settings,version_id,run_id=None,*,loop_task='',loop_pass=0):
    from ..characters.context import validate_scene_participants
    from ..evidence import render_fragments
    scene=repo.get_scene(scene_id);view=repo.context_view(scene.story_id) if hasattr(repo,'context_view') else repo
    scene=view.get_scene(scene_id);story=view.get_story(scene.story_id)
    validate_scene_participants(view,story,scene)
    ref=view.get_version(version_id)
    if ref.story_id!=story.id or ref.scene_id!=scene.id or ref.stale or not ref.complete:
        raise ValueError('Робоча копія редактури недоступна або застаріла')
    text=view.read_text(ref.id)
    if settings.edit_mode=='prose':
        from .context import build_context
        ctx=build_context(view,scene_id,'edit',settings,editor_source_id=version_id)
    else:
        sections=[text] if settings.edit_mode=='diff' else [f'ЧЕРНЕТКА [version_id={ref.id}] — НУМЕРОВАНІ ФРАГМЕНТИ\n'+render_fragments(text)]
        ctx=make_context(view,story,scene,'edit',settings,sections,[ref.id],{'copyedit_draft_id':ref.id})
    fragments={'copyedit_draft_id':ref.id}
    if run_id:fragments.update(edit_loop_run_id=run_id,edit_loop_task_cursor=loop_task,edit_loop_pass_index=str(loop_pass))
    ctx.fragments.update(fragments)
    return ctx


def check_base(repo,run):
    data=progress(run)
    scene=repo.get_scene(scene_id(run))
    base=repo.get_version(data['base_version_id'])
    target=TargetCAS.model_validate(data['target_cas'])
    if (scene.revision!=data['scene_revision'] or scene.heads.get('prose')!=target.version_id
            or scene.head_revisions.get('prose',0)!=target.head_revision
            or compare_snapshot(repo.context_view(run.story_id),base.dependency_snapshot)):
        raise ValueError('Джерело або сцена змінилися під час редактури; збережені проходи не застосовано')


def readiness(repo,request,run=None):
    result=dict(ready=False,reason=None,roles={},calls=request.edit_pass_limit,evaluator=None,warnings=[])
    try:
        if run and progress(run):
            check_base(repo,run)
            if progress(run).get('proposal_attempt_id'):raise ValueError('Спершу прийміть підсумкові правки; нових викликів не потрібно')
            attempts=model_attempts(repo,run)
            completed=next((a for a in reversed(attempts) if completed_pass(a,run)),None)
            local_stop=completed and (completed.context.get('edit_loop_stop') or repo.get_version(completed.result_version_id).sha256 in progress(run)['seen_hashes'])
            if progress(run).get('stop_reason') or len(attempts)>=request.edit_pass_limit or local_stop or recoverable_failed_pass(repo,run):
                result.update(ready=True,calls=0)
                return result
        settings=role(repo,request.story_id)
        result['roles']={'editor':settings.provider.model_dump(include={'provider','model'})}
        if run and progress(run):
            version_id=progress(run)['current_version_id']
            result['calls']=max(0,request.edit_pass_limit-len(model_attempts(repo,run)))
        else:
            scene,ref=source(repo,scene_id(run) if run else request.scene_id,prefer_draft=bool(run and pipeline(run)));version_id=ref.id
            if scene.story_id!=request.story_id:raise ValueError('Сцена належить іншому твору')
            result['warnings'].append('Джерело: чернетка.' if run and pipeline(run) else 'Джерело: поточна проза.' if scene.heads.get('prose') else 'Джерело: чернетка.')
        context(repo,scene_id(run) if run else request.scene_id,settings,version_id)
        if settings.provider.provider in {'venice','openrouter'} and repo.billing('summary',scope='story:'+request.story_id)['limit_nanos'] is None:
            raise ValueError('Спершу задайте явний ліміт бюджету в налаштуваннях')
        result['ready']=True
    except (ValueError,KeyError) as exc:
        result['reason']=str(exc) if isinstance(exc,ValueError) else 'Оберіть доступну сцену'
    return result


def save_pass_result(repo,attempt,ctx,original,text):
    """Called only after the selected editor protocol and its guards succeeded."""
    run=repo.get_run(ctx.fragments['edit_loop_run_id'])
    if (run.request.mode!='edit_loop' and not pipeline(run)) or run.story_id!=ctx.story_id or scene_id(run)!=ctx.scene_id or ctx.fragments.get('edit_loop_task_cursor','')!=task_key(run):
        raise ValueError('Невідповідний запуск багатопрохідної редактури')
    if original==text:
        attempt.context['edit_loop_stop']='no_changes'
        attempt.result_version_id=ctx.fragments['copyedit_draft_id']
    else:
        ref=repo.save_version(ctx.story_id,ctx.scene_id,'draft',text,ctx.input_refs,run.id,dependency_snapshot=ctx.dependency_snapshot)
        attempt.result_version_id=ref.id
    attempt.state='completed'
    return repo.save_attempt(attempt)


def model_attempts(repo,run):
    return [a for a in repo.list_attempts(run.story_id,run.id)
            if a.context.get('fragments',{}).get('edit_loop_run_id')==run.id and a.context.get('fragments',{}).get('edit_loop_task_cursor','')==task_key(run) and not a.context.get('edit_loop_summary')]


def initialize(worker,run):
    repo=worker.repo;scene,ref=source(repo,scene_id(run),prefer_draft=pipeline(run))
    settings=role(repo,run.story_id)
    ctx=context(repo,scene.id,settings,ref.id)
    base=repo.save_version(run.story_id,scene.id,'draft',repo.read_text(ref.id),ctx.input_refs,run.id,dependency_snapshot=ctx.dependency_snapshot)
    with worker.condition:
        current=worker.get_run(run.id)
        data=dict(source_version_id=ref.id,base_version_id=base.id,current_version_id=base.id,
            scene_revision=scene.revision,target_cas=ctx.target_cas.model_dump(),candidate_version_ids=[],
            seen_hashes=[base.sha256],stop_reason=None,proposal_attempt_id=None,attempt_count=0,pass_cursor=0)
        if pipeline(current):current.editor_loops[task_key(current)]=data
        else:current.editor_loop=data
        worker._save(current)


STOP_NAMES={'no_changes':'Редактор не запропонував нових змін','limit':'Досягнуто ліміту проходів','cycle':'Виявлено повтор попереднього тексту',
    'pass_failed':'Цикл зупинено після невдалого проходу; показано результати успішних'}


def stop_after_failure(worker,run,attempt):
    """Persist the local-only stop before summary creation, retaining the failed attempt."""
    data=progress(run)
    data.update(stop_reason='pass_failed',failed_attempt_id=attempt.id,failure_message=attempt.error,
        attempt_count=len(model_attempts(worker.repo,run)))
    worker._save(run)
    finish(worker,run,'pass_failed')


def finish(worker,run,reason):
    from ..rewrite_diff import build_rewrite_diff,rewrite_warnings
    repo=worker.repo;check_base(repo,run);data=progress(run)
    before=repo.read_text(data['base_version_id']);after=repo.read_text(data['current_version_id'])
    summary=None
    if before!=after:
        proposal=build_rewrite_diff(before,after)
        first=next(a for a in model_attempts(repo,run) if a.state=='completed')
        ctx=ContextBundle.model_validate({k:v for k,v in first.context.items() if k in ContextBundle.model_fields})
        # First pass is anchored to the immutable initial copy, not an intermediate draft.
        summary=next((a for a in repo.list_attempts(run.story_id,run.id) if a.context.get('edit_loop_summary',{}).get('task_cursor','')==task_key(run) and a.context.get('edit_loop_summary')),None)
        if summary is None:
            id=new_id()
            summary=StageAttempt(id=id,run_id=run.id,story_id=run.story_id,scene_id=scene_id(run),stage='edit',state='needs_review',
                context=ctx.model_dump(),partial_path=f'stories/{run.story_id}/runs/{id}/partial.txt')
            summary.context.update(copyedit_proposal={'protocol_version':2,'draft_id':data['base_version_id'],'proposal':proposal.model_dump()},
                edit_loop_summary={'run_id':run.id,'attempt_ids':[a.id for a in model_attempts(repo,run)],'stop_reason':reason,'task_cursor':task_key(run)},
                editor_warnings=rewrite_warnings(before,after,proposal.edits),run_cursor=run.cursor)
            if reason=='pass_failed':
                summary.context['edit_loop_summary'].update(failed_attempt_id=data['failed_attempt_id'],
                    failure_message=data.get('failure_message'),
                    successful_attempt_ids=[a.id for a in model_attempts(repo,run) if a.state=='completed'])
            with repo.files.open_partial(summary.partial_path) as out:out.write(after.encode('utf-8'))
            repo.save_attempt(summary)
    with worker.condition:
        current=worker.get_run(run.id)
        data=progress(current)
        pause=current.state in {'pause_requested','paused'} or 'edit' in current.request.pause_after
        data.update(stop_reason=reason,proposal_attempt_id=summary.id if summary else None,attempt_count=len(model_attempts(repo,current)))
        advance=False
        # Respect cancellation arriving while a local summary was being built.
        if current.state in {'cancelled','cancellation_requested'} or worker.cancel_event.is_set():
            current.state='cancelled'
        else:
            current.state='needs_review' if summary else 'completed'
        current.error=None
        if pipeline(current) and not summary and current.state!='cancelled':
            scene=repo.get_scene(scene_id(current));selected=scene.heads.get('prose')
            usable=selected and repo.get_version(selected).complete and not repo.get_version(selected).stale and repo.read_text(selected)==before
            current.state='running' if usable else 'failed'
            if usable and pause:current.state='paused'
            advance=bool(usable)
            if not usable:current.error='Редактор не запропонував змін. Немає актуальної прийнятої прози з цим текстом; пам’ять не запускалася.'
        current.warning=STOP_NAMES[reason]+f". Спроб: {data['attempt_count']} із {current.request.edit_pass_limit}."+(' Перегляньте спільні правки.' if summary else ' Сумарних змін немає; прийняття недоступне.')
        if reason=='pass_failed':
            count=sum(a.state=='completed' for a in model_attempts(repo,current))
            current.warning+=f" Успішних проходів: {count}. Причина зупинки: {data.get('failure_message') or 'Невдалий прохід редактора'}."
        if advance:current.cursor+=1
        worker._save(current)
        worker.event(run.id,'state',{'state':current.state,'warning':current.warning,'error':current.error})


def execute(worker,id):
    from pydantic import ValidationError
    try:
        _execute(worker,id)
    except Exception as exc:
        with worker.condition:
            run=worker.get_run(id)
            if progress(run):progress(run)['attempt_count']=len(model_attempts(worker.repo,run))
            run.state='cancelled' if worker.cancel_event.is_set() else 'failed'
            run.error=str(exc) if isinstance(exc,(ValueError,ContextOverflow)) and not isinstance(exc,ValidationError) else 'Не вдалося завершити цикл редактури; збережені проходи доступні в історії. Автоматичного повтору немає.'
            worker._save(run);worker.event(id,'state',{'state':run.state,'error':run.error})


def _execute(worker,id):
    from .stages import execute_stage
    repo=worker.repo
    run=worker.get_run(id)
    if not progress(run):initialize(worker,run)
    while True:
        with worker.condition:
            run=worker.get_run(id)
            if worker.cancel_event.is_set() or run.state in {'cancelled','cancellation_requested'}:
                run.state='cancelled';worker._save(run);worker.event(id,'state',{'state':run.state});return
            if run.state in {'pause_requested','paused'}:
                run.state='paused';worker._save(run);worker.event(id,'state',{'state':run.state});return
            if progress(run).get('proposal_attempt_id'):return
            run.state='running';worker._save(run)
        check_base(repo,run)
        if progress(run).get('stop_reason'):
            finish(worker,run,progress(run)['stop_reason']);return
        attempts=model_attempts(repo,run)
        completed=next((a for a in reversed(attempts) if completed_pass(a,run)),None)
        failed=recoverable_failed_pass(repo,run)
        if completed is None and failed:
            with worker.condition:stop_after_failure(worker,worker.get_run(id),failed)
            return
        if completed is None and len(attempts)>=run.request.edit_pass_limit:
            finish(worker,run,'limit');return
        if completed is None:
            settings=role(repo,run.story_id)
            ctx=context(repo,scene_id(run),settings,progress(run)['current_version_id'],run.id,loop_task=task_key(run),loop_pass=pass_index(run))
            worker.event(id,'stage_started',dict(stage='edit',scene_id=scene_id(run),model=settings.provider.model,
                provider=settings.provider.provider,estimated_tokens=ctx.estimated_tokens,edit_loop_pass=len(attempts)+1,edit_loop_limit=run.request.edit_pass_limit))
            completed=execute_stage(repo,scene_id(run),'edit',ctx,worker.gateway_factory(settings.provider),worker.cancel_event,
                lambda text:worker.event(id,'delta',{'stage':'edit','scene_id':scene_id(run),'text':text}),id,run.cursor)
        with worker.condition:
            current=worker.get_run(id)
            progress(current)['attempt_count']=len(model_attempts(repo,current))
            worker.event(id,'stage_finished',dict(attempt_id=completed.id,state=completed.state,usage=completed.usage,finish_reason=completed.finish_reason))
            if completed.state!='completed':
                if worker.cancel_event.is_set() or current.state in {'cancelled','cancellation_requested'}:
                    current.state='cancelled';worker._save(current)
                    worker.event(id,'state',{'state':current.state});return
                if completed.state=='failed' and completed.context.get('edit_loop_failure_origin')=='model_response' and progress(current)['current_version_id']!=progress(current)['base_version_id']:
                    stop_after_failure(worker,current,completed);return
                current.state=completed.state;current.error=completed.error;worker._save(current)
                worker.event(id,'state',{'state':current.state,'error':current.error});return
            result=repo.get_version(completed.result_version_id)
            stop=completed.context.get('edit_loop_stop')
            if not stop:
                progress(current)['candidate_version_ids'].append(result.id)
                if result.sha256 in progress(current)['seen_hashes']:stop='cycle'
                else:
                    progress(current)['current_version_id']=result.id
                    progress(current)['seen_hashes'].append(result.sha256)
            if pipeline(current):progress(current)['pass_cursor']+=1
            else:current.cursor+=1
            if stop:progress(current)['stop_reason']=stop
            worker._save(current)
        if stop:finish(worker,current,stop);return
        if len(model_attempts(repo,current))>=current.request.edit_pass_limit:finish(worker,current,'limit');return
        if 'edit' in current.request.pause_after:
            with worker.condition:
                current=worker.get_run(id);current.state='pause_requested';worker._save(current)
