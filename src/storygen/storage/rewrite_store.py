"""One transaction publishes draft, decision and cleared working notes."""
import hashlib
from ..domain import StageAttempt,VersionRef,RevisionConflict,new_id,now
from ..authoring.comments import CommentSet
from ..dependency_models import DependencySnapshot
from ..copyediting import apply_proposal,validate_indices
from ..sentence_groups import validate_group_selection
from .context_view import ContextView
from .comment_store import _latest,_insert_comment_set
from .invalidation import invalidate_in_transaction


def publish_rewrite_selection(repo,scene_id,attempt_id,indices,expected_revision,fingerprint,expected_comments_revision):
    from ..rewriting import proposal_data,ensure_current
    attempt=repo.get_attempt(attempt_id)
    _,source,original,proposal,_,_,_=proposal_data(repo.context_view(attempt.story_id),attempt)
    indices=validate_indices(indices,len(proposal.edits));validate_group_selection(original,proposal,indices,source.content_format)
    text=apply_proposal(original,proposal,indices)
    ref=None
    if indices and text!=original:
        id=new_id();raw=text.encode('utf-8')
        ref=VersionRef(id=id,story_id=attempt.story_id,scene_id=scene_id,kind='draft',sha256=hashlib.sha256(raw).hexdigest(),
            relative_path=f'stories/{attempt.story_id}/versions/{id}.txt',input_refs=attempt.context['input_refs'],source_run_id=attempt.run_id,
            content_format=source.content_format,dependency_snapshot=DependencySnapshot.model_validate(attempt.context['dependency_snapshot']))
        repo.files.write(ref.relative_path,raw)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        attempt=repo._get(db,'stage_attempts',attempt_id,StageAttempt)
        if attempt.scene_id!=scene_id:raise ValueError('Пропозиція належить іншій сцені')
        view=ContextView(repo,db,attempt.story_id)
        scene,source,original,proposal,_,actual,notes=proposal_data(view,attempt)
        if scene.revision!=expected_revision or actual!=fingerprint or notes.revision!=expected_comments_revision:
            raise RevisionConflict('Сцену, коментарі або пропозицію змінено')
        ensure_current(view,attempt,scene,source,notes,_latest(db,scene.id))
        indices=validate_indices(indices,len(proposal.edits));validate_group_selection(original,proposal,indices,source.content_format)
        if ref:
            if (ref.input_refs!=attempt.context['input_refs'] or ref.dependency_snapshot!=DependencySnapshot.model_validate(attempt.context['dependency_snapshot']) or
                ref.content_format!=source.content_format or repo.files.read(ref.relative_path,ref.sha256).decode('utf-8')!=apply_proposal(original,proposal,indices)):
                raise ValueError('Результат не відповідає вибраним змінам')
            db.execute('INSERT INTO versions VALUES(?,?,?,?,?)',(ref.id,ref.story_id,ref.scene_id,ref.kind,ref.model_dump_json()))
            db.executemany('INSERT INTO dependency_edges VALUES(?,?)',[(id,ref.id) for id in set(ref.input_refs)])
            scene.heads['draft']=ref.id;scene.head_revisions['draft']=scene.head_revisions.get('draft',0)+1;scene.revision+=1
            repo._save_scene(db,scene)
            invalidate_in_transaction(repo,db,[source.id],exclude=[ref.id])
            repo._touch_story(db,scene.story_id)
            cleared=CommentSet(story_id=scene.story_id,scene_id=scene.id,revision=notes.revision+1,source_version_id=ref.id,source_sha256=ref.sha256,content_format=ref.content_format)
            _insert_comment_set(db,cleared)
        attempt.context.setdefault('rewrite_decisions',[]).append(dict(id=new_id(),created_at=now(),source_version_id=source.id,comment_set_id=notes.id,
            selected_indices=indices,result_version_id=ref.id if ref else None,proposal_fingerprint=fingerprint))
        attempt.state='completed';attempt.error=None;attempt.result_version_id=ref.id if ref else None
        db.execute('UPDATE stage_attempts SET state=?,payload=? WHERE id=?',(attempt.state,attempt.model_dump_json(),attempt.id))
        if attempt.run_id:
            from ..run_models import Run,RunEvent
            run=repo._get(db,'runs',attempt.run_id,Run)
            if run.state in {'needs_review','alternative'}:
                run.state='completed';run.cursor=len(run.tasks);run.error=None
                db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(run.state,run.model_dump_json(),run.id))
                seq=db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM run_events WHERE run_id=?',(run.id,)).fetchone()[0]
                event=RunEvent(run_id=run.id,seq=seq,type='state',data={'state':run.state})
                db.execute('INSERT INTO run_events VALUES(?,?,?,?)',(run.id,seq,event.type,event.model_dump_json()))
    return dict(scene=repo.get_scene(scene_id),version=ref,attempt=attempt,comment_set=repo.get_comment_set(scene_id))
