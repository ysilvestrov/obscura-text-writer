"""Offline structural/proof checks; old assessments may legitimately be non-current."""
import json
from ..impact.models import ImpactRecord,ImpactApplication,fingerprint,TEXT_STAMP_EXCLUDE
from ..impact.validation import validate_delta,validate_check,validate_memory_input,decode_response
from ..domain import StageAttempt
from .integrity import contained_path


def check_impact(db,report,stories,scenes,versions,root):
    records={};actions=[]
    for key,raw in db.execute("SELECT key,payload FROM app_settings WHERE key LIKE 'impact:%' ORDER BY rowid"):
        try:
            parts=key.split(':')
            if len(parts)!=4 or parts[1] not in stories:raise ValueError('Owner')
            model=ImpactRecord if parts[2]=='report' else ImpactApplication if parts[2]=='application' else None
            if not model:raise ValueError('Kind')
            item=model.model_validate_json(raw)
            if item.id!=parts[3] or item.story_id!=parts[1]:raise ValueError('Key')
            if isinstance(item,ImpactApplication):actions.append(item);continue
            records[item.id]=item;t=item.target;ref=versions[t.version_id]
            if ref.story_id!=item.story_id or ref.scene_id!=t.scene_id or t.story_id!=item.story_id or ref.sha256!=t.sha256 or ref.content_format!=t.content_format:
                raise ValueError('Target owner/hash')
            if t.fingerprint!=fingerprint(t.model_dump(exclude=TEXT_STAMP_EXCLUDE)):raise ValueError('Target stamp')
            if t.group_id!=fingerprint([c.model_dump() for c in sorted(t.changes,key=lambda c:c.id) if c.changed]):raise ValueError('Group stamp')
            if contained_path(root,ref.relative_path).read_text(encoding='utf-8')!=t.text:raise ValueError('Target text')
            for id,sha in t.source_hashes.items():
                source=versions[id]
                if source.story_id!=item.story_id or source.sha256!=sha or not source.complete:raise ValueError('Source')
            if item.schema_version==2:
                from ..impact.chunk_validation import verify_chunk_record
                proofs={}
                for id in item.proof_attempt_ids.values():
                    row=db.execute('SELECT payload FROM stage_attempts WHERE id=?',(id,)).fetchone()
                    if not row:raise ValueError('Proof missing')
                    proofs[id]=StageAttempt.model_validate_json(row[0])
                verify_chunk_record(item,proofs,lambda path:contained_path(root,path).read_text(encoding='utf-8'))
                continue
            for id,stage in [(item.attempt_id,'impact_check'),(item.delta_attempt_id,'impact_delta')]:
                row=db.execute('SELECT payload FROM stage_attempts WHERE id=?',(id,)).fetchone()
                if not row:raise ValueError('Proof missing')
                attempt=StageAttempt.model_validate_json(row[0])
                if attempt.story_id!=item.story_id or attempt.run_id!=item.run_id or attempt.state!='completed' or attempt.stage!=stage or attempt.finish_reason!='stop':raise ValueError('Proof state')
                payload=decode_response(contained_path(root,attempt.partial_path).read_text(encoding='utf-8'))
                normalized=(validate_check if stage=='impact_check' else validate_delta)(payload,t).model_dump()
                if normalized!=attempt.context.get('impact_result'):raise ValueError('Proof body')
                if stage=='impact_check':
                    if attempt.context.get('impact_target')!=t.model_dump():raise ValueError('Proof target')
                    check=validate_check(payload,t)
                    validate_memory_input(attempt.context,t,check)
                    if check.materials[0]!=item.verdict:raise ValueError('Proof verdict')
                else:validate_delta(payload,t)
        except (ValueError,KeyError,TypeError,OSError):report.add('invalid_impact',key,'Некоректний звіт перевірки впливу або його джерела')
    for action in actions:
        record=records.get(action.record_id)
        if not record or action.story_id!=record.story_id or action.version_id!=record.target.version_id:
            report.add('invalid_impact_application',action.id,'Невідповідне застосування звіту')
