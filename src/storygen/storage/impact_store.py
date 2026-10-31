"""Atomic report publication; never impersonates an author acceptance."""
import json
from ..domain import StageAttempt,RevisionConflict
from ..run_models import Run
from ..impact.models import ImpactRecord,ImpactApplication,fingerprint,TEXT_STAMP_EXCLUDE
from ..impact.planning import capture_target
from ..impact.validation import validate_delta,validate_check,validate_memory_input,decode_response
from .context_view import ContextView
from .impact_validity import current_record


def _insert(db,key,record):
    db.execute('INSERT INTO app_settings(key,payload) VALUES(?,?)',(key,record.model_dump_json()))


def _proof(repo,db,record):
    run=repo._get(db,'runs',record.run_id,Run)
    if run.story_id!=record.story_id or run.request.mode!='impact' or run.state in {'cancelled','cancellation_requested'}:
        raise ValueError('Запуск перевірки недоступний або скасований')
    if record.schema_version==2:
        from ..impact.chunk_validation import verify_chunk_record
        attempts={id:repo._get(db,'stage_attempts',id,StageAttempt) for id in record.proof_attempt_ids.values()}
        verify_chunk_record(record,attempts,repo.files.read_partial)
        return
    for id,stage in [(record.attempt_id,'impact_check'),(record.delta_attempt_id,'impact_delta')]:
        attempt=repo._get(db,'stage_attempts',id,StageAttempt)
        if (attempt.story_id!=record.story_id or attempt.run_id!=record.run_id or attempt.stage!=stage
            or attempt.state!='completed' or attempt.finish_reason!='stop' or not repo.files.read_partial(attempt.partial_path).strip()):
            raise ValueError('Немає завершеного доказу перевірки впливу')
        raw=decode_response(repo.files.read_partial(attempt.partial_path))
        normalized=(validate_check if stage=='impact_check' else validate_delta)(raw,record.target).model_dump()
        if normalized!=attempt.context.get('impact_result'):raise ValueError('Первинна відповідь не відповідає звіту')
        if stage=='impact_check':
            if attempt.scene_id!=record.target.scene_id:raise ValueError('Перевірка іншої сцени')
            if attempt.context.get('impact_target')!=record.target.model_dump():raise ValueError('Інший знімок перевірки')
            result=validate_check(attempt.context['impact_result'],record.target)
            validate_memory_input(attempt.context,record.target,result)
            if result.materials[0]!=record.verdict or result.memory_semantic_impact!=record.memory_semantic_impact or result.memory_explanation!=record.memory_explanation:
                raise ValueError('Висновок відрізняється від відповіді моделі')
        else:
            if attempt.context.get('impact_target',{}).get('group_id')!=record.target.group_id:raise ValueError('Дельта іншої бази')
            result=validate_delta(attempt.context['impact_result'],record.target)
            if result.uncertainty and record.verdict.verdict!='uncertain':raise ValueError('Невизначена дельта не очищує текст')


def save_report(repo,record):
    record=ImpactRecord.model_validate(record)
    if record.target.fingerprint!=fingerprint(record.target.model_dump(exclude=TEXT_STAMP_EXCLUDE)):raise ValueError('Невідповідний знімок звіту')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE');view=ContextView(repo,db,record.story_id)
        existing=view.impact_records.get(record.id)
        if existing:
            if existing!=record:raise ValueError('ID звіту вже використаний')
            return existing
        _proof(repo,db,record)
        scene=view.get_scene(record.target.scene_id)
        live=capture_target(view,record.target.version_id)
        if live.blockers or live.fingerprint!=record.target.fingerprint or scene.heads.get(record.target.material)!=record.target.version_id:
            raise RevisionConflict('Передумови змінилися; звіт збережено у спробі без застосування')
        _insert(db,'impact:'+record.story_id+':report:'+record.id,record)
        application=ImpactApplication(story_id=record.story_id,record_id=record.id,version_id=record.target.version_id,action='apply')
        _insert(db,'impact:'+record.story_id+':application:'+application.id,application)
    return record


def reject_report(repo,story_id,record_id):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE');view=ContextView(repo,db,story_id)
        record=view.impact_records[record_id]
        if record.story_id!=story_id:raise ValueError('Сторонній звіт')
        actions=[a for a in view.impact_applications if a.record_id==record_id]
        if actions and actions[-1].action=='reject':return actions[-1]
        action=ImpactApplication(story_id=story_id,record_id=record_id,version_id=record.target.version_id,action='reject')
        _insert(db,'impact:'+story_id+':application:'+action.id,action)
        return action


def state(repo,story_id):
    from ..impact.memory_review import capture_memory
    view=repo.context_view(story_id);rows=[]
    for record in view.impact_records.values():
        current=current_record(view,record.target.version_id)
        is_current=bool(current and current.id==record.id)
        scene=view.scenes.get(record.target.scene_id)
        memory=capture_memory(view,scene) if scene and not scene.trashed_at else {}
        memory_current=bool(is_current and record.target.memory_id and memory.get('memory_id')==record.target.memory_id
            and memory.get('memory_sha256')==record.target.memory_sha256 and memory.get('memory_source_hashes')==record.target.memory_source_hashes)
        needs_update=bool(scene and not scene.trashed_at and scene.heads.get('memory') and view.get_version(scene.heads['memory']).stale)
        rows.append(dict(record=record,current=is_current,memory_needs_update=needs_update or memory.get('memory_evidence_status') in {'invalid','historical'} or memory_current and record.memory_semantic_impact=='possible',
            memory_check_current=memory_current,memory_evidence_status=memory.get('memory_evidence_status','missing')))
    return rows


def operation(repo,action,**data):
    operations={'save_report':save_report,'reject_report':reject_report,'state':state}
    if action not in operations:raise ValueError('Невідома дія перевірки впливу')
    return operations[action](repo,**data)
