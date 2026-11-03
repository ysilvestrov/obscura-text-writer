import json
import pytest
from storygen.impact.result_budget import budget_size
from storygen.impact.chunk_validation import validate_part
from tests.impact.test_reference_wire import setup_wire


def test_derived_coverage_is_not_model_output():
    data=dict(covered_ids=[str(i).zfill(64) for i in range(51)],summary='Підсумок.'*80,verdict='no_impact',findings=[],evidence=[],target_quotes=[],uncertainty=None)
    assert budget_size(data,2)<4096<budget_size(data,1)


def test_wire2_evidence_and_text_still_count():
    data=dict(covered_ids=[],summary='x'*5000,evidence=[dict(source_id='a',quote='x'*1000)])
    assert budget_size(data,2)>4096


def test_wire2_raw_cap_is_unchanged():
    m,task=setup_wire();m.result_cap=512
    raw=dict(summary='x'*600,verdict='no_impact',new_findings=[],evidence_ids=[],target_evidence_ids=[],uncertainty=None)
    with pytest.raises(ValueError):validate_part(raw,m,task,{})


@pytest.mark.parametrize('break_proof',[False,True,'source','settings'])
def test_saved_failed_check_is_reused_without_model_call(tmp_path,monkeypatch,break_proof):
    from tests.impact.test_runner import runner
    from storygen.authoring.blueprints import save_role_settings
    from storygen.providers.models import RoleSettings,ProviderSettings
    from storygen.generation.impact_context import readiness
    from storygen.run_models import RunRequest
    from storygen.providers.streaming import GenerationEvent
    from storygen.impact import chunk_validation
    from storygen.impact.chunk_models import ChunkManifest
    from storygen.generation.impact_chunk_runner import load_results,reusable
    from storygen.impact.result_budget import compact_size,LEGACY_CAP_ERROR
    repo,story,first,second,ref,worker,old,_=runner(tmp_path)
    worker.cancel(old.id)
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='local-reference',response_mode='json_schema',local_disable_thinking=True),context_tokens=32768,max_output_tokens=1024,max_input_chars=100000),repo.get_story(story.id).revision)
    request=RunRequest(story_id=story.id,mode='impact');preview=readiness(repo,request)
    assert preview['ready'],preview['reason']
    request.impact_plan_fingerprint=preview['chunk_manifest']['fingerprint'];run=worker.enqueue(request,'budget-fix');calls=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx.fingerprint);phase=json.loads(ctx.user_text)['phase']
            raw=dict(summary='x'*280 if phase=='check' else 'Перевірено.',verdict='no_impact',new_findings=[],evidence_ids=[],target_evidence_ids=[],uncertainty=None)
            yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
            yield GenerationEvent(type='terminal',finish_reason='stop',usage={'prompt_tokens':100,'completion_tokens':100})
    worker.gateway_factory=lambda _:Gateway()
    fixed=chunk_validation.validate_part
    def legacy(raw,m,task,results):
        result=fixed(raw,m,task,results)
        if compact_size(result.model_dump())>m.result_cap:raise ValueError(LEGACY_CAP_ERROR+'; текст збережено')
        return result
    monkeypatch.setattr(chunk_validation,'validate_part',legacy)
    worker._execute(run.id)
    failed=worker.get_run(run.id);assert failed.state=='failed' and failed.cursor==1
    attempt=repo.list_attempts(story.id,run.id)[-1];original_bytes=repo.files.read_partial(attempt.partial_path);usage=attempt.usage.copy()
    monkeypatch.setattr(chunk_validation,'validate_part',fixed)
    m=ChunkManifest.model_validate(failed.impact['manifest']);results=load_results(repo,failed,m)
    if break_proof in {'source','settings'}:
        if break_proof=='source':
            from storygen.generation.dependencies import save_manual_prose
            save_manual_prose(repo,first.id,'Змінено джерело.',repo.get_scene(first.id).revision)
        else:
            save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='different'),context_tokens=32768,max_output_tokens=1024),repo.get_story(story.id).revision)
        with pytest.raises(ValueError):worker.resume(run.id)
        assert repo.get_attempt(attempt.id).state=='failed' and len(calls)==2
        return
    if break_proof:
        attempt.context['api_request']['messages'][1]['content']='changed body'
        repo.save_attempt(attempt)
        with pytest.raises(ValueError,match='API-запит'):worker.resume(run.id)
        assert repo.get_attempt(attempt.id).state=='failed' and len(calls)==2
        return
    worker.resume(run.id)
    repaired=repo.get_attempt(attempt.id)
    assert repaired is not None and repaired.id==attempt.id and repaired.state=='completed'
    assert repaired.error is None and repaired.usage==usage
    assert repaired.context['validation_history'][-1]['previous_error']==attempt.error
    assert repo.files.read_partial(attempt.partial_path)==original_bytes and len(calls)==2
    assert worker.get_run(run.id).state=='queued' and worker.get_run(run.id).cursor==1
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    assert calls.count(attempt.context['fingerprint'])==1


@pytest.mark.parametrize('change',[{'state':'cancelled'},{'finish_reason':'length'},{'error':'Відмова моделі'},{'stage':'memory'}])
def test_only_known_completed_budget_failure_is_recoverable(change):
    from types import SimpleNamespace
    from storygen.impact.result_budget import recoverable_failure,LEGACY_CAP_ERROR
    a=dict(stage='impact_part',state='failed',finish_reason='stop',error=LEGACY_CAP_ERROR)
    assert not recoverable_failure(SimpleNamespace(**{**a,**change}))


def test_wire2_expanded_evidence_still_rejects_overflow():
    from storygen.impact.chunking import task_payload
    from storygen.impact.reference_wire import build_wire
    m,task=setup_wire();m.result_cap=512
    _,registry,_=build_wire(m,task_payload(m,task,{}))
    raw=dict(summary='Перевірено.',verdict='no_impact',new_findings=[],evidence_ids=[next(iter(registry))]*8,target_evidence_ids=[],uncertainty=None)
    assert len(json.dumps(raw,ensure_ascii=False,separators=(',',':')))<m.result_cap
    with pytest.raises(ValueError,match='модельних даних'):
        validate_part(raw,m,task,{})
