"""Atomic unchanged-prose publication bound to a validated editor pass."""
import hashlib
from ..domain import StageAttempt,VersionRef,RevisionConflict,new_id
from ..run_models import Run,RunEvent
from ..dependency_models import DependencySnapshot,TargetCAS
from .context_view import ContextView
from .snapshots import compare_snapshot
from .invalidation import invalidate_in_transaction


def _data(run,key):
    if key=='':
        if run.request.mode!='edit_loop':raise ValueError('Невідповідний цикл редактури')
        data=run.editor_loop;scene_id=run.request.scene_id
    else:
        if run.request.mode not in {'scene','remaining'} or key!=str(run.cursor):raise ValueError('Етап циклу змінився')
        task=run.tasks[run.cursor]
        if not task.get('editor_loop') or task.get('stage')!='edit':raise ValueError('Невідповідний етап редактури')
        data=run.editor_loops.get(key);scene_id=task['scene_id']
    if not data or data.get('stop_reason')!='no_changes' or data['current_version_id']!=data['base_version_id']:
        raise ValueError('Немає підтвердженої редактури без змін')
    return data,scene_id


def _check(repo,db,run,key,attempt_id):
    data,scene_id=_data(run,key);view=ContextView(repo,db,run.story_id);scene=view.get_scene(scene_id)
    base=view.get_version(data['base_version_id']);attempt=repo._get(db,'stage_attempts',attempt_id,StageAttempt)
    fragments=attempt.context.get('fragments',{})
    if (attempt.story_id!=run.story_id or attempt.scene_id!=scene.id or attempt.run_id!=run.id or attempt.stage!='edit'
            or attempt.state!='completed' or attempt.finish_reason!='stop' or attempt.context.get('edit_loop_stop')!='no_changes'
            or attempt.result_version_id!=base.id or fragments.get('edit_loop_run_id')!=run.id
            or fragments.get('edit_loop_task_cursor','')!=key or fragments.get('copyedit_draft_id')!=base.id
            or base.kind!='draft' or not base.complete or base.stale or not repo.files.read_partial(attempt.partial_path).strip()):
        raise ValueError('Редактура не має валідованої повної відповіді без змін')
    target=TargetCAS.model_validate(data['target_cas'])
    if (target.scene_id!=scene.id or target.head!='prose' or scene.revision!=data['scene_revision']
            or scene.heads.get('prose')!=target.version_id or scene.head_revisions.get('prose',0)!=target.head_revision):
        raise RevisionConflict('Сцену або прозу змінено; автоматичне збереження без змін скасовано')
    snapshot=DependencySnapshot.model_validate(attempt.context['dependency_snapshot'])
    if set(snapshot.refs)!=set(attempt.context['input_refs']) or base.id not in snapshot.refs or compare_snapshot(view,snapshot):
        raise RevisionConflict('Джерела редактури змінилися; прозу автоматично не замінено')
    text=view.read_text(base.id)
    if not text.strip():raise ValueError('Порожній текст не може стати прозою')
    return data,scene,base,attempt,view,snapshot,text


def publish_unchanged_prose(repo,run_id,key,attempt_id):
    with repo.db.connection() as db:
        db.execute('BEGIN');run=repo._get(db,'runs',run_id,Run)
        if run.state in {'cancelled','cancellation_requested'}:return None
        data,scene,base,attempt,view,snapshot,text=_check(repo,db,run,key,attempt_id)
        if data.get('no_change_prose_version_id'):
            ref=view.get_version(data['no_change_prose_version_id'])
            if ref.id!=scene.heads.get('prose') or ref.stale or not ref.complete or ref.content_format!=base.content_format or view.read_text(ref.id)!=text:
                raise RevisionConflict('Автоматично збережену прозу змінено')
            return ref
        selected=view.get_version(scene.heads['prose']) if scene.heads.get('prose') else None
        reuse=bool(selected and selected.complete and not selected.stale and selected.content_format==base.content_format and view.read_text(selected.id)==text)
    ref=selected if reuse else VersionRef(id=new_id(),story_id=run.story_id,scene_id=scene.id,kind='edited',
        sha256=hashlib.sha256(text.encode()).hexdigest(),relative_path='',input_refs=attempt.context['input_refs'],
        source_run_id=run.id,dependency_snapshot=snapshot,content_format=base.content_format)
    if not reuse:
        ref.relative_path=f'stories/{run.story_id}/versions/{ref.id}.txt';repo.files.write(ref.relative_path,text.encode())
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE');run=repo._get(db,'runs',run_id,Run)
        if run.state in {'cancelled','cancellation_requested'}:return None
        data,scene,base,attempt,view,snapshot,text=_check(repo,db,run,key,attempt_id)
        if data.get('no_change_prose_version_id'):return view.get_version(data['no_change_prose_version_id'])
        if ref.content_format!=base.content_format or repo.files.read(ref.relative_path,ref.sha256).decode()!=text:
            raise ValueError('Результат не збігається з перевіреним незмінним текстом')
        if not reuse:
            if ref.input_refs!=attempt.context['input_refs'] or ref.dependency_snapshot!=snapshot:raise ValueError('Залежності прози змінилися')
            db.execute('INSERT INTO versions VALUES(?,?,?,?,?)',(ref.id,ref.story_id,ref.scene_id,ref.kind,ref.model_dump_json()))
            db.executemany('INSERT INTO dependency_edges VALUES(?,?)',[(id,ref.id) for id in set(ref.input_refs)])
            previous=scene.heads.get('prose');scene.heads['prose']=ref.id;scene.head_revisions['prose']=scene.head_revisions.get('prose',0)+1
            scene.revision+=1;scene.needs_review=False;repo._save_scene(db,scene)
            if previous:invalidate_in_transaction(repo,db,[previous],exclude=[ref.id])
            repo._touch_story(db,scene.story_id)
        data.update(no_change_prose_version_id=ref.id,no_change_attempt_id=attempt.id,scene_revision=scene.revision,
            target_cas=TargetCAS(scene_id=scene.id,head='prose',version_id=ref.id,head_revision=scene.head_revisions.get('prose',0)).model_dump())
        db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(run.state,run.model_dump_json(),run.id))
        seq=db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?',(run.id,)).fetchone()[0]
        event=RunEvent(run_id=run.id,seq=seq,type='editor_no_changes_published',data={'scene_id':scene.id,'version_id':ref.id,'attempt_id':attempt.id,'reused':reuse})
        db.execute('INSERT INTO run_events VALUES(?,?,?,?)',(run.id,seq,event.type,event.model_dump_json()))
    return ref
