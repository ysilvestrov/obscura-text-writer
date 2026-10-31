import json
import pytest
from tests.review.test_store import setup


def test_parts_cover_all_source_and_target_intervals(tmp_path):
    from storygen.review.planning import prepare_scene,check_specs,validate_coverage
    repo,story,first,second,ref,run,target=setup(tmp_path)
    plan=prepare_scene(repo,second.id)
    specs=plan['delta_specs']+check_specs(repo,plan,{})
    validate_coverage(plan,specs)
    assert plan['targets'][0]['version_id']==ref.id
    assert any(r['kind']=='target' for r in plan['registry'].values())
    with pytest.raises(ValueError):validate_coverage(plan,plan['delta_specs'])


def test_current_only_check_and_scoped_refs(tmp_path):
    from storygen.review.planning import prepare_scene,check_specs
    from storygen.review.wire import request_for,validate_part
    repo,story,first,second,ref,run,target=setup(tmp_path);plan=prepare_scene(repo,second.id)
    spec=check_specs(repo,plan,{})[0];payload,body,aliases=request_for(plan,spec,{})
    assert all(r.get('side')!='old' for r in payload['evidence'].values())
    assert 'summary' not in body.get('response_format',{}).get('json_schema',{}).get('schema',{}).get('properties',{})
    target_alias=next(k for k,v in payload['evidence'].items() if v['kind']=='target')
    source_alias=next(k for k,v in payload['evidence'].items() if v['kind']=='source')
    change=payload['evidence'][source_alias]['change']
    raw=dict(complete=True,concerns=[dict(kind='issue',message='Змінилася передумова.',change_refs=[change],target_refs=[target_alias],source_refs=[source_alias])],carry_refs=[target_alias])
    parsed=validate_part(raw,plan,spec,{})
    assert parsed['concerns'][0]['target_refs'][0] in plan['registry']
    assert plan['registry'][parsed['concerns'][0]['target_refs'][0]]['text'] not in json.dumps(parsed,ensure_ascii=False)
    raw['concerns'][0]['target_refs']=['FOREIGN']
    with pytest.raises(ValueError):validate_part(raw,plan,spec,{})


def test_incomplete_is_not_a_clean_result(tmp_path):
    from storygen.review.planning import prepare_scene,check_specs
    from storygen.review.wire import validate_part
    repo,story,first,second,ref,run,target=setup(tmp_path);plan=prepare_scene(repo,second.id);spec=check_specs(repo,plan,{})[0]
    with pytest.raises(ValueError,match='незаверш'):
        validate_part(dict(complete=False,concerns=[],carry_refs=[]),plan,spec,{})


def test_replay_requires_exact_api_body(tmp_path):
    from storygen.review.planning import prepare_scene,check_specs
    from storygen.review.wire import request_for,validate_part
    from storygen.review.proofs import verify_part
    from storygen.domain import StageAttempt,new_id
    repo,story,first,second,ref,run,target=setup(tmp_path);plan=prepare_scene(repo,second.id);spec=check_specs(repo,plan,{})[0]
    payload,body,aliases=request_for(plan,spec,{})
    raw=dict(complete=True,concerns=[],carry_refs=[])
    a=StageAttempt(id=new_id(),run_id=run.id,story_id=story.id,scene_id=second.id,stage='review_part',state='completed',finish_reason='stop',partial_path='proof',context=dict(api_request=body,review_spec=spec,review_plan_id=plan['id'],review_result=validate_part(raw,plan,spec,{})))
    assert verify_part(a,plan,spec,{},lambda _:json.dumps(raw),story.id,run.id)['complete']
    a.context['api_request']['messages'][1]['content']='changed'
    with pytest.raises(ValueError):verify_part(a,plan,spec,{},lambda _:json.dumps(raw),story.id,run.id)


def test_full_proof_and_registry_tampering(tmp_path):
    from storygen.review.planning import prepare_scene,check_specs,synthesis_spec
    from storygen.review.context import build
    from storygen.review.models import SceneReport
    from storygen.review.proofs import verify_report
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    import threading
    repo,story,first,second,ref,run,target=setup(tmp_path);plan=prepare_scene(repo,second.id)
    results={};specs={};proofs={};attempts={}
    class Gateway:
        def stream(self,ctx,cancel):
            phase=json.loads(ctx.user_text)['phase']
            raw=dict(complete=True,changes=[],questions=[]) if phase=='delta' else dict(complete=True,concerns=[],carry_refs=[])
            yield GenerationEvent(type='delta',text=json.dumps(raw))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    def call(spec):
        a=execute_stage(repo,second.id,'review_part',build(repo,plan,spec,results),Gateway(),threading.Event(),lambda _:None,run.id)
        assert a.state=='completed',a.error
        results[spec['id']]=a.context['review_result'];specs[spec['id']]=spec;proofs[spec['id']]=a.id;attempts[a.id]=a
    for spec in plan['delta_specs']:call(spec)
    checks=check_specs(repo,plan,results)
    for spec in checks:call(spec)
    root=synthesis_spec(repo,plan,[s['id'] for s in checks],results);call(root)
    report=SceneReport(story_id=story.id,scene_id=second.id,run_id=run.id,targets=plan['targets'],complete=True,registry=plan['registry'],part_specs=specs,proofs=proofs,coverage=dict(plan=plan,order=list(specs),roots=[root['id']]))
    assert verify_report(report,attempts,repo.files.read_partial)
    from storygen.review.store import publish_scene
    publish_scene(repo,run.id,report,'model_no_concerns','automatic')
    assert not repo.get_version(ref.id).stale
    report.registry[next(iter(report.registry))]['text']='tampered'
    with pytest.raises(ValueError):verify_report(report,attempts,repo.files.read_partial)
