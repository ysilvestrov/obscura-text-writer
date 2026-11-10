"""One saved source plus one immutable instruction set, using the writer role."""
import json
from ..authoring.comments import comment_fingerprint,validate_comment_set
from ..authoring.blueprints import get_role_settings
from .context import build_context,make_context
from .context_labels import label


def saved_inputs(repo,request):
    scene=repo.get_scene(request.scene_id)
    if scene.story_id!=request.story_id or scene.heads.get('draft')!=request.source_version_id:
        raise ValueError('Чернетку змінено; відкрийте збережену версію знову')
    source=repo.get_version(request.source_version_id)
    if source.story_id!=scene.story_id or source.scene_id!=scene.id or source.kind!='draft' or not source.complete:
        raise ValueError('Неприпустиме джерело переписування')
    notes=repo.get_comment_set(scene.id)
    if not notes or notes.id!=request.comment_set_id or comment_fingerprint(notes,source)!=request.comment_fingerprint:
        raise ValueError('Коментарі змінено; збережіть і перегляньте їх знову')
    if not notes.general.strip() and not notes.comments:raise ValueError('Додайте хоча б одну вказівку')
    if any(c.anchor.state!='valid' for c in notes.comments):raise ValueError('Спершу переприв’яжіть або видаліть змінені коментарі')
    validate_comment_set(repo.read_text(source.id),source.content_format,notes)
    return scene,source,notes


def build_rewrite_context(repo,request):
    scene,source,notes=saved_inputs(repo,request)
    role=get_role_settings(repo,scene.story_id).get('writer')
    if not role or not role.provider.model.strip():raise ValueError('Роль не налаштовано: writer')
    view=repo.context_view(scene.story_id)
    base=build_context(view,scene.id,'rewrite',role,editor_source_id=source.id)
    sections=[base.user_text,label('rewrite_notes',view.story.language)+'\n'+json.dumps({'general':notes.general,'comments':[dict(id=c.id,instruction=c.instruction,quote=c.anchor.display_quote,start=c.anchor.start,end=c.anchor.end) for c in notes.comments]},ensure_ascii=False)]
    fragments={**base.fragments,'rewrite_notes':notes.model_dump_json(),'rewrite_comment_fingerprint':request.comment_fingerprint}
    ctx=make_context(view,view.story,view.get_scene(scene.id),'rewrite',role,sections,list(base.input_refs),fragments,
        accepted_prose_ids=base.accepted_stale_prose_ids,memory_metrics=base.memory_metrics,context_warnings=base.context_warnings,
        memory_provenance=base.dependency_snapshot.memory_provenance)
    saved_inputs(repo,request) # No mixed source/notes after context capture.
    return ctx


def readiness(repo,request):
    result=dict(ready=False,reason=None,roles={},calls=1,evaluator=None,warnings=[])
    try:
        ctx=build_rewrite_context(repo,request)
        result['roles']={'writer':ctx.settings.provider.model_dump(include={'provider','model'})}
        result['warnings']=ctx.context_warnings
        if ctx.settings.provider.provider in {'venice','openrouter'} and repo.billing('summary',scope='story:'+request.story_id)['limit_nanos'] is None:
            raise ValueError('Спершу задайте явний ліміт бюджету в налаштуваннях')
        result['ready']=True
    except (ValueError,KeyError) as exc:result['reason']=str(exc) if isinstance(exc,ValueError) else 'Матеріал не знайдено'
    return result


def save_rewrite_result(repo,attempt,context,text):
    from ..rewrite_diff import build_rewrite_diff
    from ..storage.snapshots import compare_snapshot
    from ..authoring.comments import CommentSet,comment_fingerprint
    from .edit_classification import text_refusal
    if text_refusal(text):raise ValueError('Письменник відмовився переписувати текст; автоматичного повтору немає')
    source_id=context.fragments['rewrite_source_id']
    original=repo.read_text(source_id)
    proposal=build_rewrite_diff(original,text)
    if not proposal.edits:
        attempt.state='completed';attempt.context['rewrite_no_changes']=True
        return repo.save_attempt(attempt)
    raw=dict(protocol_version=2,source_id=source_id,proposal=proposal.model_dump())
    attempt.context['rewrite_proposal']=raw
    notes=CommentSet.model_validate_json(context.fragments['rewrite_notes'])
    latest=repo.get_comment_set(attempt.scene_id)
    scene=repo.get_scene(attempt.scene_id)
    changed=scene.heads.get('draft')!=source_id or not latest or latest.id!=notes.id
    if not changed:
        changed=latest.source_version_id!=source_id or comment_fingerprint(latest,repo.get_version(source_id))!=context.fragments['rewrite_comment_fingerprint']
    changed=changed or bool(compare_snapshot(repo.context_view(attempt.story_id),context.dependency_snapshot))
    attempt.state='alternative' if changed else 'needs_review'
    attempt.error='Джерела змінено; результат збережено як альтернативу' if changed else 'Перегляньте зміни письменника; поточну чернетку не змінено'
    return repo.save_attempt(attempt)
