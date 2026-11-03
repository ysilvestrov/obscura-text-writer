"""Storage-side semantic validity. Original snapshots and evidence remain untouched."""
import json
from ..domain import StageAttempt
from ..impact.models import ImpactRecord,ImpactApplication,fingerprint,TEXT_STAMP_EXCLUDE
from ..impact.validation import validate_delta,validate_check,validate_memory_input,decode_response
from ..impact.planning import capture_target


def load(db,story_id):
    records={};applications=[]
    for key,raw in db.execute('SELECT key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid',('impact:'+story_id+':%',)):
        if key.startswith('impact:'+story_id+':report:'):
            record=ImpactRecord.model_validate_json(raw)
            if record.story_id!=story_id or key!='impact:'+story_id+':report:'+record.id:raise ValueError('Пошкоджений звіт впливу')
            records[record.id]=record
        elif key.startswith('impact:'+story_id+':application:'):
            action=ImpactApplication.model_validate_json(raw)
            if action.story_id!=story_id or key!='impact:'+story_id+':application:'+action.id:raise ValueError('Пошкоджене застосування впливу')
            applications.append(action)
        else:raise ValueError('Невідомий запис перевірки впливу')
    for action in applications:
        record=records.get(action.record_id)
        if not record or action.version_id!=record.target.version_id:raise ValueError('Невідповідний звіт застосування')
    proofs={}
    for id in {id for record in records.values() for id in [record.attempt_id,record.delta_attempt_id,*record.proof_attempt_ids.values()]}:
        row=db.execute('SELECT payload FROM stage_attempts WHERE id=?',(id,)).fetchone()
        if row:
            try:proofs[id]=StageAttempt.model_validate_json(row[0])
            except ValueError:pass
    return records,applications,proofs


def latest(view,version_id):
    records=[r for r in view.impact_records.values() if r.target.version_id==version_id]
    if not records:return None
    record=records[-1]
    actions=[a for a in view.impact_applications if a.record_id==record.id]
    if not actions or actions[-1].action!='apply':return None
    return record


def current_record(view,version_id):
    cache=view.impact_current_cache
    if version_id in cache:return cache[version_id]
    cache[version_id]=None
    record=latest(view,version_id)
    if not record:return None
    try:
        scene=view.get_scene(record.target.scene_id)
        if scene.heads.get(record.target.material)!=version_id:return None
        if record.target.fingerprint!=fingerprint(record.target.model_dump(exclude=TEXT_STAMP_EXCLUDE)):return None
        if record.schema_version==2:
            from ..impact.chunk_validation import verify_chunk_record
            verify_chunk_record(record,view.impact_proofs,view.files.read_partial)
        else:
            for id,stage in [(record.attempt_id,'impact_check'),(record.delta_attempt_id,'impact_delta')]:
                attempt=view.impact_proofs.get(id)
                if not attempt or attempt.story_id!=view.story.id or attempt.run_id!=record.run_id or attempt.stage!=stage or attempt.state!='completed' or attempt.finish_reason!='stop':return None
                raw=decode_response(view.files.read_partial(attempt.partial_path))
                result=(validate_check if stage=='impact_check' else validate_delta)(raw,record.target)
                if result.model_dump()!=attempt.context.get('impact_result'):return None
                if stage=='impact_check':
                    validate_memory_input(attempt.context,record.target,result)
                    if attempt.context.get('impact_target')!=record.target.model_dump() or attempt.scene_id!=scene.id:return None
                    if result.materials[0]!=record.verdict or result.memory_semantic_impact!=record.memory_semantic_impact or result.memory_explanation!=record.memory_explanation:return None
                elif attempt.context.get('impact_target',{}).get('group_id')!=record.target.group_id or result.uncertainty and record.verdict.verdict!='uncertain':return None
        live=capture_target(view,version_id)
        if live.blockers or live.fingerprint!=record.target.fingerprint:return None
        cache[version_id]=record
        return record
    except (KeyError,ValueError,OSError):return None


def valid_overlay(view,version_id):
    record=current_record(view,version_id)
    return record if record and record.verdict.verdict=='no_impact' else None
