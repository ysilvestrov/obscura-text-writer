import json
from pathlib import Path
import pytest
from storygen.impact.chunk_models import ChunkManifest
from storygen.impact.chunking import task_payload
from storygen.impact.chunk_requests import request_for
from storygen.impact.chunk_validation import validate_manifest, validate_part
from storygen.impact.reference_wire import build_wire, quote_windows


def fixture():
    return json.loads(Path('tests/impact/fixtures/legacy-part-wire1.json').read_text(encoding='utf-8'))


def test_legacy_fixture_replay():
    f=fixture();m=validate_manifest(f['manifest']);task=next(t for t in m.tasks if t['id']==f['task_id'])
    system,user,body=request_for(m,task_payload(m,task,{}))
    assert body==f['context']['api_request']
    assert user==f['context']['user_text']
    assert validate_part(f['response'],m,task,{}).model_dump()==f['response']


def setup_wire():
    f=fixture();m=ChunkManifest.model_validate(f['manifest']);m.wire_schema_version=2;m.result_cap=6000
    task=next(t for t in m.tasks if t['id']==f['task_id'])
    return m,task


def test_windows_cover_without_loss():
    text='Текст. '*150
    windows=quote_windows(text)
    assert all(w in text and len(w)<=160 for w in windows)
    assert windows[0]==text[:160] and windows[-1].endswith(text[-10:])


def test_refs_are_exact_and_scoped():
    m,task=setup_wire();payload=task_payload(m,task,{})
    wire,registry,aliases=build_wire(m,payload)
    assert wire['phase']=='delta' and registry
    raw=dict(summary='Перевірено.',verdict='no_impact',new_findings=[],evidence_ids=[next(iter(registry))],target_evidence_ids=[],uncertainty=None)
    result=validate_part(raw,m,task,{})
    assert result.covered_ids==task['coverage']
    assert result.evidence[0].quote in payload['documents'].values()
    raw['target_evidence_ids']=raw['evidence_ids']
    with pytest.raises(ValueError):validate_part(raw,m,task,{})


def test_unknown_reference_rejected():
    m,task=setup_wire()
    raw=dict(summary='Перевірено.',verdict='no_impact',new_findings=[],evidence_ids=['E999999'],target_evidence_ids=[],uncertainty=None)
    with pytest.raises(ValueError):validate_part(raw,m,task,{})


def test_reducer_preserves_findings_and_uncertainty():
    from storygen.impact.models import Finding,Evidence
    from storygen.impact.chunk_models import PartResultV2
    m,leaf=setup_wire()
    change=m.units[leaf['units'][0]]['change_id']
    quote=next(iter(task_payload(m,leaf,{})['documents'].values()))
    finding=Finding(target_quote='Цільова фраза.',change_ids=[change],explanation='Виправити.',evidence=[Evidence(source_id=change+':old',quote=quote)])
    child=PartResultV2(covered_ids=[],summary='Зміна.',verdict='changes_required',findings=[finding],evidence=[],target_quotes=['Цільова фраза.'],uncertainty='Бракує контексту.')
    task=dict(phase='reduce_check',units=[],dependencies=['child'],coverage=['child'])
    raw=dict(summary='Зведено.',verdict='changes_required',new_findings=[],evidence_ids=[],target_evidence_ids=[],uncertainty=None)
    result=validate_part(raw,m,task,{'child':child.model_dump()})
    assert result.findings==[finding] and result.uncertainty
    raw['verdict']='no_impact'
    with pytest.raises(ValueError):validate_part(raw,m,task,{'child':child.model_dump()})


@pytest.mark.parametrize('with_finding',[False,True])
@pytest.mark.parametrize('qualified',[False,True])
def test_native_local_run_and_proof_replay(tmp_path,with_finding,qualified):
    from tests.impact.test_runner import runner
    from storygen.authoring.blueprints import save_role_settings
    from storygen.providers.models import RoleSettings,ProviderSettings
    from storygen.generation.impact_context import readiness
    from storygen.run_models import RunRequest
    from storygen.providers.streaming import GenerationEvent
    repo,story,first,second,ref,worker,old,calls=runner(tmp_path)
    worker.cancel(old.id)
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='local-reference',response_mode='json_schema',local_disable_thinking=True),context_tokens=32768,max_output_tokens=4096,max_input_chars=100000),repo.get_story(story.id).revision)
    request=RunRequest(story_id=story.id,mode='impact')
    if qualified:
        from tests.token_budget.test_local_counter import artifacts
        from storygen.impact.planning import plan_impact
        from storygen.impact.chunking import plan_chunks
        from storygen.token_budget.local_profiles import register,activate
        t,p=artifacts(tmp_path)
        sample=plan_chunks(repo,plan_impact(repo.context_view(story.id)))
        b=dict(model='local-reference',messages=[dict(role='system',content=sample.prompt_text),dict(role='user',content='{}')],reasoning_effort='none',response_format=dict(type='json_schema',json_schema=dict(name='impact_part',strict=True,schema={})))
        profile=register(repo.root,'http://localhost:1235/v1',b,t,p,[dict(request=b,observed_tokens=len(sample.prompt_text.split())+1)])
        activate(repo.root,profile['id'])
    preview=readiness(repo,request)
    assert preview['ready'],preview['reason']
    assert preview['wire_schema_version']==2
    request.impact_plan_fingerprint=preview['chunk_manifest']['fingerprint']
    run=worker.enqueue(request,'reference-wire');calls=[]
    issued=[]
    class Gateway:
        def stream(self,ctx,cancel):
            calls.append(ctx)
            if qualified:assert ctx.estimate_method=='qualified_local_tokenizer'
            assert ctx.api_request['reasoning_effort']=='none'
            data=json.loads(ctx.user_text)
            assert 'new_findings' in ctx.api_request['response_format']['json_schema']['schema']['properties']
            assert 'required_coverage' not in data
            raw=dict(summary='Перевірено.',verdict='no_impact',new_findings=[],evidence_ids=[],target_evidence_ids=[],uncertainty=None)
            inherited=any(c['findings'] for c in data['results'].values())
            if data['phase']=='check' and with_finding and not issued and data['allowed_change_ids']:
                registry=data['evidence_registry'];change=data['allowed_change_ids'][0]
                source=next(k for k,v in registry.items() if v['kind']=='source' and v['source_id'].rsplit(':',1)[0]==change);target=next(k for k,v in registry.items() if v['kind']=='target')
                raw['new_findings']=[dict(target_evidence_id=target,change_ids=[change],explanation='Уточніть подію.',evidence_ids=[source])]
                issued.append(True)
            if inherited or raw['new_findings']:raw['verdict']='changes_required'
            yield GenerationEvent(type='delta',text=json.dumps(raw,ensure_ascii=False))
            yield GenerationEvent(type='terminal',finish_reason='stop')
    worker.gateway_factory=lambda _:Gateway()
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed',worker.get_run(run.id).error
    rows=repo.impact('state',story_id=story.id)
    assert rows and rows[-1]['current']
    assert len(calls)==preview['calls']
    assert len(rows[-1]['record'].verdict.findings)==int(with_finding)
    if qualified:
        (repo.root/'local_tokenizers'/profile['id']/'tokenizer.json').unlink()
        assert repo.impact('state',story_id=story.id)[-1]['current']


def test_delta_schema_cannot_demand_scene_changes():
    m,task=setup_wire();m.settings.provider.response_mode='json_schema'
    _,_,body=request_for(m,task_payload(m,task,{}))
    schema=body['response_format']['json_schema']['schema']
    assert schema['properties']['verdict']['enum']==['no_impact','uncertain']
    assert schema['properties']['new_findings']['maxItems']==0


def test_legacy_raw_attempt_is_still_a_valid_proof():
    from types import SimpleNamespace
    from storygen.impact.chunk_validation import verify_attempt
    f=fixture();m=validate_manifest(f['manifest']);task=next(t for t in m.tasks if t['id']==f['task_id'])
    attempt=SimpleNamespace(story_id=f['story_id'],run_id=f['run_id'],scene_id=f['scene_id'],stage='impact_part',state='completed',finish_reason='stop',context=f['context'],partial_path='fixture')
    assert verify_attempt(attempt,m,task,{},lambda _:json.dumps(f['response'],ensure_ascii=False),f['story_id'],f['run_id']).model_dump()==f['response']


def test_child_quote_registry_is_within_preview_reserve():
    from storygen.impact.chunk_models import PartResultV2
    from storygen.impact.models import Evidence
    from storygen.generation.impact_chunk_context import measure_payload
    m,_=setup_wire();m.result_cap=1433;m.settings.provider.response_mode='json_schema'
    cid=m.plan.targets[0].changes[0].id
    child=PartResultV2(covered_ids=['a'*64],summary='😀'*170,verdict='no_impact',findings=[],evidence=[Evidence(source_id=cid+':new',quote='😀'*100)],target_quotes=['😀'+str(i) for i in range(12)],uncertainty=None)
    assert len(json.dumps(child.model_dump(),ensure_ascii=False,separators=(',',':')))<=m.result_cap
    real=dict(phase='reduce_check',results={str(i):child.model_dump() for i in range(2)})
    planned=dict(phase='reduce_check',results={str(i):{'reserved_result':'😀'*m.result_cap} for i in range(2)})
    actual=measure_payload(None,m,real)[3]['body_bytes'];upper=measure_payload(None,m,planned)[3]['body_bytes']
    assert actual<=upper


def test_literal_machine_addresses_are_never_aliased():
    m,task=setup_wire();payload=task_payload(m,task,{})
    literal=next(iter(m.plan.targets[0].changes)).id
    key=payload['sources'][0]['document_id'];payload['documents'][key]=literal
    wire,registry,_=build_wire(m,payload)
    doc=wire['sources'][0]['document_id']
    assert wire['documents'][doc]==literal
    e=next(e for e in registry.values() if e['quote']==literal)
    assert any(v['quote']==e['quote'] for v in wire['evidence_registry'].values())


def test_uncertain_child_can_coexist_with_new_confirmed_findings():
    from storygen.impact.reference_wire import wire_schema
    from storygen.impact.chunk_models import PartResultV2
    m,task=setup_wire();payload=task_payload(m,task,{})
    payload['phase']='check';payload['target']=dict(id='target',version_id='version',document_id='doc',text='Текст цілі.')
    payload['results']={'child':PartResultV2(covered_ids=[],summary='Зміна.',verdict='uncertain',findings=[],evidence=[],uncertainty='Невідомо.').model_dump()}
    wire,registry,_=build_wire(m,payload)
    assert set(wire_schema(registry,wire)['properties']['verdict']['enum'])=={'uncertain','changes_required'}
