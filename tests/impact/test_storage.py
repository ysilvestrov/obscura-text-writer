import json
import pytest
from storygen.impact.models import ImpactRecord,MaterialVerdict
from storygen.impact.planning import capture_target
from storygen.storage.repository import Repository
from storygen.domain import StageAttempt,new_id
from storygen.run_models import Run,RunRequest
from storygen.generation.dependencies import save_manual_prose
from tests.impact.test_planning import seeded


def assessed(root):
    repo,story,first,second,ref=seeded(root)
    save_manual_prose(repo,first.id,'Марія знає про лист. Вечір настав.',repo.get_scene(first.id).revision)
    target=capture_target(repo.context_view(story.id),ref.id)
    run=Run(id=new_id(),story_id=story.id,request_id=new_id(),request=RunRequest(story_id=story.id,mode='impact'),tasks=[])
    repo.enqueue_run(run)
    delta=StageAttempt(id=new_id(),run_id=run.id,story_id=story.id,scene_id=second.id,stage='impact_delta',state='completed',finish_reason='stop',context={'impact_result':dict(covered_change_ids=[c.id for c in target.changes if c.changed],items=[],uncertainty=None),'impact_target':target.model_dump()},partial_path=f'stories/{story.id}/runs/delta.txt')
    check=StageAttempt(id=new_id(),run_id=run.id,story_id=story.id,scene_id=second.id,stage='impact_check',state='completed',finish_reason='stop',context={},partial_path=f'stories/{story.id}/runs/check.txt')
    verdict=MaterialVerdict(version_id=ref.id,verdict='no_impact',covered_change_ids=[c.id for c in target.changes if c.changed],explanation='Нова деталь не суперечить сцені.',findings=[])
    record=ImpactRecord(story_id=story.id,run_id=run.id,attempt_id=check.id,target=target,delta_attempt_id=delta.id,verdict=verdict,memory_semantic_impact='unchecked',memory_explanation='Пам’ять окрема.')
    check.context={'impact_target':target.model_dump(),'impact_result':dict(materials=[verdict.model_dump()],memory_semantic_impact='unchecked',memory_explanation='Пам’ять окрема.')}
    for a in [delta,check]:
        repo.files.write(a.partial_path,json.dumps(a.context['impact_result'],ensure_ascii=False).encode());repo.save_attempt(a)
    return repo,story,first,second,ref,record


def test_overlay_invalidated_and_rejected(tmp_path):
    repo,story,first,second,ref,record=assessed(tmp_path)
    assert repo.get_version(ref.id).stale
    repo.impact('save_report',record=record)
    assert not repo.get_version(ref.id).stale
    assert not repo.get_scene(second.id).needs_review
    repo.impact('reject_report',story_id=story.id,record_id=record.id)
    assert repo.get_version(ref.id).stale


def test_new_input_and_corruption_never_hidden_by_overlay(tmp_path):
    repo,story,first,second,ref,record=assessed(tmp_path)
    repo.impact('save_report',record=record)
    save_manual_prose(repo,first.id,'Марія забула про лист.',repo.get_scene(first.id).revision)
    assert repo.get_version(ref.id).stale
    with pytest.raises(ValueError):repo.impact('save_report',record=record.model_copy(update={'id':new_id()}))


def test_only_completed_owned_proof_can_apply(tmp_path):
    repo,story,first,second,ref,record=assessed(tmp_path)
    a=repo.get_attempt(record.attempt_id);a.state='failed';repo.save_attempt(a)
    with pytest.raises(ValueError):repo.impact('save_report',record=record)
    assert repo.get_version(ref.id).stale

def test_review_of_source_invalidates_downstream_assessment(tmp_path):
    repo,story,first,second,ref,record=assessed(tmp_path)
    repo.impact('save_report',record=record)
    # A newly attached review state on an actual dependency changes the baseline.
    source=repo.get_scene(first.id).heads['prose']
    from storygen.impact.models import ImpactApplication
    import json
    source_record=record.model_copy(deep=True)
    source_record.id=new_id();source_record.target.version_id=source;source_record.target.scene_id=first.id
    action=ImpactApplication(story_id=story.id,record_id=source_record.id,version_id=source,action='apply')
    with repo.db.connection() as db:
        db.execute('INSERT INTO app_settings VALUES(?,?)',('impact:'+story.id+':report:'+source_record.id,source_record.model_dump_json()))
        db.execute('INSERT INTO app_settings VALUES(?,?)',('impact:'+story.id+':application:'+action.id,action.model_dump_json()))
    assert repo.get_version(ref.id).stale

def test_missing_model_proof_revokes_effective_freshness(tmp_path):
    repo,story,first,second,ref,record=assessed(tmp_path)
    repo.impact('save_report',record=record)
    assert not repo.get_version(ref.id).stale
    attempt=repo.get_attempt(record.attempt_id)
    repo.files.resolve(attempt.partial_path).write_text('broken proof',encoding='utf-8')
    assert repo.get_version(ref.id).stale
