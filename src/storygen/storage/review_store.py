"""Atomic review authority and exact live bindings; no model I/O in transactions."""
import json
from ..domain import RevisionConflict,StageAttempt
from ..run_models import Run
from ..impact.models import fingerprint,TEXT_STAMP_EXCLUDE
from ..review.capture import for_report
from ..storage.context_view import ContextView
from ..review.models import SceneReport,ReviewAcceptance


def prefix(story_id):return 'review3:'+story_id+':'


def load(db,story_id):
    reports={};acceptances=[];operations={}
    for key,raw in db.execute('SELECT key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid',(prefix(story_id)+'%',)):
        data=json.loads(raw)
        suffix=key[len(prefix(story_id)):]
        if suffix.startswith('report:'):
            record=SceneReport.model_validate(data)
            if record.story_id!=story_id or key!=prefix(story_id)+'report:'+record.id:raise ValueError('Пошкоджений звіт перевірки сцен')
            reports[record.id]=record
        elif suffix.startswith('acceptance:'):
            record=ReviewAcceptance.model_validate(data)
            if record.story_id!=story_id or key!=prefix(story_id)+'acceptance:'+record.id:raise ValueError('Пошкоджений запис прийняття сцени')
            acceptances.append(record)
        elif suffix.startswith('operation:'):operations[suffix[len('operation:'):]]=data
        else:raise ValueError('Невідомий запис послідовного перегляду')
    ids={id for report in reports.values() for id in report.proofs.values()};proofs={}
    for id in ids:
        row=db.execute('SELECT payload FROM stage_attempts WHERE id=?',(id,)).fetchone()
        if row:proofs[id]=StageAttempt.model_validate_json(row[0])
    return reports,acceptances,operations,proofs


def latest(view,version_id):
    return next((a for a in reversed(view.review_acceptances) if a.target.version_id==version_id),None)


def current_acceptance(view,version_id):
    if version_id in view.review_current_cache:return view.review_current_cache[version_id]
    view.review_current_cache[version_id]=None
    record=latest(view,version_id)
    if not record:return None
    try:
        report=view.review_reports[record.report_id]
        if report.story_id!=record.story_id or report.scene_id!=record.scene_id or report.run_id!=record.run_id:return None
        scene=view.get_scene(record.scene_id)
        if scene.heads.get(record.target.material)!=version_id:return None
        ref=view.versions[version_id]
        if not ref.complete or ref.sha256!=record.target.sha256:return None
        view.read_blob(ref.relative_path,ref.sha256)
        if record.authority=='model_no_concerns':
            from ..review.proofs import verify_report
            verify_report(report,view.review_proofs,view.files.read_partial)
            if not report.complete or report.concerns:return None
        live=for_report(view,version_id,report)
        if live.blockers or live.fingerprint!=record.target.fingerprint:return None
        # A stored operation authenticates both author decisions and automatic checkpoints.
        operation=view.review_operations.get(record.operation_id)
        if not operation or not any(a==record.model_dump() for a in operation['result']['acceptances']):return None
        view.review_current_cache[version_id]=record
        return record
    except (ValueError,KeyError,OSError):return None


def _put(db,key,value):db.execute('INSERT INTO app_settings VALUES(?,?)',(key,json.dumps(value,ensure_ascii=False)))


def operation(repo,story_id,operation_id):
    with repo.db.connection() as db:
        repo._active_story(db,story_id)
        row=db.execute('SELECT payload FROM app_settings WHERE key=?',(prefix(story_id)+'operation:'+operation_id,)).fetchone()
    return json.loads(row[0]) if row else None


def save_dispositions(repo,run_id,expected,operation_id,command,choices):
    from ..review.decisions import _preview
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE');current=repo._get(db,'runs',run_id,Run)
        live=_preview(repo,ContextView(repo,db,current.story_id),current)
        if live['fingerprint']!=expected or live.get('changed_while_waiting') or current.state!='needs_review':raise RevisionConflict('Стан перевірки змінився')
        result=dict(state='needs_review',phase='author_editing',acceptances=[])
        current.impact.update(phase='author_editing',dispositions=choices)
        _put(db,prefix(current.story_id)+'operation:'+operation_id,dict(command=command,fingerprint=fingerprint(command),result=result))
        db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(current.state,current.model_dump_json(),run_id))
    return result


def save_report(repo,run,report):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current=repo._get(db,'runs',run.id,Run)
        if current.state in {'cancelled','cancellation_requested'}:return
        view=ContextView(repo,db,run.story_id)
        for target in report.targets:
            if view.get_scene(target.scene_id).heads.get(target.material)!=target.version_id or for_report(view,target.version_id,report).fingerprint!=target.fingerprint:raise RevisionConflict('Матеріали змінилися під час пошуку')
        _put(db,prefix(run.story_id)+'report:'+report.id,report.model_dump())
        current.impact.update(phase='awaiting_author',current_report_id=report.id,dispositions={})
        current.state='needs_review';current.error=None
        db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(current.state,current.model_dump_json(),current.id))


def publish_scene(repo,run_id,report,authority,operation_id,*,accepted_targets=None,dispositions=None,command=None):
    report=SceneReport.model_validate(report)
    targets=accepted_targets or report.targets
    payload=dict(report=report.model_dump(),authority=authority,targets=[t.model_dump() for t in targets],dispositions=dispositions or {},command=command)
    stamp=fingerprint(payload)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        run=repo._get(db,'runs',run_id,Run);base=prefix(run.story_id)
        key=base+'operation:'+operation_id
        saved=db.execute('SELECT payload FROM app_settings WHERE key=?',(key,)).fetchone()
        if saved:
            saved=json.loads(saved[0])
            if saved['fingerprint']!=stamp:raise ValueError('ID рішення вже використаний з іншими даними')
            return saved['result']
        if report.run_id!=run.id or report.story_id!=run.story_id or run.impact.get('protocol')!=3:raise ValueError('Звіт належить іншій перевірці')
        if run.state in {'cancelled','cancellation_requested','completed','failed'}:raise RevisionConflict('Запуск уже зупинено')
        order=run.impact['scene_order'];cursor=run.impact['scene_cursor']
        if cursor>=len(order) or order[cursor]!=report.scene_id:raise RevisionConflict('Поточну сцену перевірки змінено')
        if authority not in {'model_no_concerns','author_rejected','author_revised'}:raise ValueError('Невідома підстава прийняття')
        if authority=='model_no_concerns':
            if not report.complete or report.concerns or not report.proofs:raise ValueError('Немає повного результату без зауважень')
            from ..review.proofs import verify_report
            proofs={id:repo._get(db,'stage_attempts',id,StageAttempt) for id in report.proofs.values()}
            verify_report(report,proofs,repo.files.read_partial)
        view=ContextView(repo,db,run.story_id)
        if command:
            from ..review.decisions import _preview
            live_preview=_preview(repo,view,run)
            if run.state!='needs_review' or live_preview.get('changed_while_waiting') or live_preview['fingerprint']!=command['expected']:raise RevisionConflict('Матеріали або рішення змінилися після перегляду')
        if not targets or any(t.scene_id!=report.scene_id or t.story_id!=run.story_id for t in targets):raise ValueError('Сторонні матеріали прийняття')
        if len({t.material for t in targets})!=len(targets):raise ValueError('Повтор матеріалу прийняття')
        for target in targets:
            live=for_report(view,target.version_id,report)
            if live.blockers or live.fingerprint!=target.fingerprint or view.get_scene(report.scene_id).heads.get(target.material)!=target.version_id:raise RevisionConflict('Матеріали або передумови змінилися після перегляду')
        saved_report=db.execute('SELECT payload FROM app_settings WHERE key=?',(base+'report:'+report.id,)).fetchone()
        if saved_report:
            if SceneReport.model_validate_json(saved_report[0])!=report:raise ValueError('ID звіту має інший вміст')
        else:_put(db,base+'report:'+report.id,report.model_dump())
        acceptances=[]
        # Publish brief before prose so prose binds to the accepted brief authority.
        for target in sorted(targets,key=lambda t:0 if t.material=='brief' else 1):
            target=for_report(ContextView(repo,db,run.story_id),target.version_id,report)
            acceptance=ReviewAcceptance(story_id=run.story_id,scene_id=report.scene_id,run_id=run.id,report_id=report.id,target=target,authority=authority,operation_id=operation_id)
            _put(db,base+'acceptance:'+acceptance.id,acceptance.model_dump());acceptances.append(acceptance.model_dump())
        scene=repo._active_scene(db,report.scene_id)
        if any(t.material=='prose' for t in targets):scene.needs_review=False
        scene.revision+=1;repo._save_scene(db,scene);repo._touch_story(db,scene.story_id)
        result=dict(report_id=report.id,acceptances=acceptances)
        _put(db,key,dict(fingerprint=stamp,result=result,dispositions=dispositions or {},command=command))
        run.impact.update(phase='memory_refresh',current_report_id=report.id,acceptance_operation=operation_id,pending_memory=True)
        run.state='running' if authority=='model_no_concerns' else 'queued';run.error=None
        db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(run.state,run.model_dump_json(),run.id))
        return result
