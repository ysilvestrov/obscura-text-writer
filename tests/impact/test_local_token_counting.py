import json
from pathlib import Path
from types import SimpleNamespace
from storygen.impact.chunk_validation import validate_manifest,verify_attempt
from storygen.impact.chunking import plan_chunks
from storygen.generation.impact_chunk_context import measure_payload
from storygen.token_budget.local_profiles import register,activate,deactivate
from tests.token_budget.test_local_counter import artifacts
from tests.impact.test_chunking import large_plan
from storygen.authoring.blueprints import save_role_settings


def test_legacy_wire2_raw_proof_without_counter():
    f=json.loads(Path('tests/impact/fixtures/legacy-part-wire2.json').read_text(encoding='utf-8'))
    m=validate_manifest(f['manifest']);assert m.local_token_counter is None
    task=next(t for t in m.tasks if t['id']==f['task_id'])
    a=SimpleNamespace(story_id=f['story_id'],run_id=f['run_id'],scene_id=f['scene_id'],stage='impact_part',state='completed',finish_reason='stop',context=f['context'],partial_path='fixture')
    assert verify_attempt(a,m,task,{},lambda _:json.dumps(f['response'],ensure_ascii=False),f['story_id'],f['run_id']).model_dump()==f['context']['impact_result']


def seeded(root):
    repo,plan=large_plan(root/'story')
    from storygen.authoring.blueprints import get_role_settings
    role=get_role_settings(repo,plan.story_id)['planner'].model_copy(deep=True)
    role.provider.response_mode='json_schema';role.provider.local_disable_thinking=True
    role.context_tokens=32768;role.max_output_tokens=4096;role.max_input_chars=100000
    save_role_settings(repo,plan.story_id,'planner',role,repo.get_story(plan.story_id).revision)
    baseline=plan_chunks(repo,plan)
    t,p=artifacts(root)
    body=dict(model=role.provider.model,messages=[dict(role='system',content=baseline.prompt_text),dict(role='user',content='{}')],reasoning_effort='none',response_format=dict(type='json_schema',json_schema=dict(name='impact_part',strict=True,schema={})))
    profile=register(repo.root,role.provider.base_url,body,t,p,[dict(request=body,observed_tokens=len(baseline.prompt_text.split())+1)])
    activate(repo.root,profile['id'])
    return repo,plan,profile,baseline


def test_qualified_manifest_has_full_coverage_and_fewer_parts(tmp_path):
    repo,plan,profile,baseline=seeded(tmp_path)
    m=plan_chunks(repo,plan);validate_manifest(m.model_dump())
    assert m.local_token_counter['id']==profile['id']
    assert len(m.tasks)<len(baseline.tasks)
    from storygen.impact.chunking import task_payload
    for task in m.tasks:
        _,_,_,estimate,_=measure_payload(repo,m,task_payload(m,task,{},planning=True))
        assert estimate['method']=='qualified_local_tokenizer'
        assert estimate['input_tokens']<=m.settings.context_tokens-m.settings.max_output_tokens
    deactivate(repo.root,profile['id'])
    _,_,_,fallback,_=measure_payload(repo,m,task_payload(m,m.tasks[0],{}),verify_counter_files=True)
    assert fallback['method']=='utf8_body_conservative'
    assert 'local_counter_not_active' in fallback['reasons']


def test_qualified_packing_does_not_query_empirical_profiles(tmp_path,monkeypatch):
    repo,plan,profile,baseline=seeded(tmp_path)
    def unexpected(*args,**kwargs):raise AssertionError('empirical query in exact counter')
    monkeypatch.setattr(repo,'token_records',unexpected)
    m=plan_chunks(repo,plan)
    assert m.local_token_counter['id']==profile['id']


def test_planning_handle_is_reused_but_dispatch_reloads(tmp_path,monkeypatch):
    from storygen.token_budget import local_profiles
    from storygen.generation.impact_chunk_context import build_chunk_context
    repo,plan,profile,baseline=seeded(tmp_path)
    original=local_profiles.load_counter;calls=[]
    def observed(*args,**kwargs):
        calls.append(kwargs.get('verify_bytes'));return original(*args,**kwargs)
    monkeypatch.setattr(local_profiles,'load_counter',observed)
    m=plan_chunks(repo,plan)
    assert calls==[True]
    build_chunk_context(repo,m,m.tasks[0],{})
    assert calls==[True,True]
