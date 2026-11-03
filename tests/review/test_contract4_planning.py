import copy
import pytest
from tests.review.test_store import setup


def prepare(tmp_path):
    from storygen.review import planning
    assert hasattr(planning,'premise_specs'), 'Контракт4 ще не інтегровано у планувальник'
    repo,story,first,second,ref,run,target=setup(tmp_path)
    return repo,planning.prepare_scene(repo,second.id,contract_version=4)


def test_premises_include_diagonal_and_complete_pairs(tmp_path):
    from storygen.review.planning import validate_coverage,check_specs
    from storygen.review import planning
    repo,plan=prepare(tmp_path)
    premises=planning.premise_specs(repo,plan,{})
    checks=check_specs(repo,plan,{})
    specs=[*plan['delta_specs'],*premises,*checks]
    validate_coverage(plan,specs)
    assert premises and all(any(a==b for a,b in s['premise_pairs']) for s in premises)
    # Pair coverage is explicit; sources fitting together must not require O(n²) calls.
    assert len(premises)==len({t['material'] for t in plan['targets']})
    with pytest.raises(ValueError):validate_coverage(plan,[s for s in specs if s!=premises[0]])


def test_wire4_has_no_model_complete_or_kind_and_preserves_partial(tmp_path):
    from storygen.review.wire import request_for,validate_part
    from storygen.review.planning import check_specs
    repo,plan=prepare(tmp_path);spec=check_specs(repo,plan,{})[0]
    payload,body,aliases=request_for(plan,spec,{})
    assert payload['contract_version']==4
    schema=body.get('response_format',{}).get('json_schema',{}).get('schema') or payload['response_schema']
    assert 'complete' not in schema['properties']
    assert 'analysis_status' in schema['properties']
    assert 'kind' not in str(schema)
    source=next(k for k,v in payload['evidence'].items() if v['kind']=='source')
    target=next(k for k,v in payload['evidence'].items() if v['kind']=='target')
    def ep(id):return dict(ref=id,start=0,end=len(payload['evidence'][id]['text']),quote=payload['evidence'][id]['text'])
    good=dict(type='contradiction',left=ep(source),right=ep(target),explanation='Конкретна несумісність.')
    bad=copy.deepcopy(good);bad['right']['quote']='Підробка'
    result=validate_part(dict(analysis_status='done',reason=None,candidates=[good,bad]),plan,spec,{})
    assert result['execution_state']=='partial' and len(result['concerns'])==1
    assert len(result['rejected'])==1
    unable=validate_part(dict(analysis_status='unable',reason='Недостатньо контексту',candidates=[]),plan,spec,{})
    assert unable['execution_state']=='partial'


def test_wire4_scope_and_budget_remain_fail_closed(tmp_path):
    from storygen.review.wire import validate_part
    from storygen.review.planning import check_specs
    repo,plan=prepare(tmp_path);spec=check_specs(repo,plan,{})[0]
    with pytest.raises(ValueError):validate_part(dict(analysis_status='done',reason=None,candidates=[],complete=True),plan,spec,{})
    tiny={**plan,'result_cap':4}
    with pytest.raises(ValueError):validate_part(dict(analysis_status='done',reason=None,candidates=[]),tiny,spec,{})


def test_legacy_plan_and_request_remain_unversioned(tmp_path):
    from storygen.review.planning import prepare_scene,check_specs
    from storygen.review.wire import request_for
    repo,story,first,second,ref,run,target=setup(tmp_path)
    plan=prepare_scene(repo,second.id)
    assert 'contract_version' not in plan
    payload,_,_=request_for(plan,check_specs(repo,plan,{})[0],{})
    assert 'contract_version' not in payload


def test_delta_change_id_is_delivered_and_accepted(tmp_path):
    from storygen.review.wire import request_for,validate_part
    repo,plan=prepare(tmp_path);spec=plan['delta_specs'][0]
    payload,_,_=request_for(plan,spec,{})
    sources=payload['evidence']
    old=next(k for k,v in sources.items() if v['side']=='old')
    new=next(k for k,v in sources.items() if v['side']=='new' and v.get('change_ref')==sources[old].get('change_ref'))
    assert sources[old].get('change_ref')
    raw=dict(analysis_status='done',reason=None,candidates=[],changes=[dict(change_ref=sources[old]['change_ref'],before='Раніше',current='Тепер',before_refs=[old],source_refs=[new])])
    assert validate_part(raw,plan,spec,{})['changes'][0]['change_ref']==sources[old]['change_ref']


def test_check_receives_machine_owned_unresolved_premises(tmp_path):
    from storygen.review.wire import request_for,validate_part
    from storygen.review.planning import premise_specs
    from storygen.review.planning4 import check_specs
    repo,plan=prepare(tmp_path);premise=premise_specs(repo,plan,{})[0]
    p,_,_=request_for(plan,premise,{})
    refs=list(p['evidence'])[:2]
    def ep(ref):return dict(ref=ref,start=0,end=len(p['evidence'][ref]['text']),quote=p['evidence'][ref]['text'])
    result=validate_part(dict(analysis_status='done',reason=None,candidates=[dict(type='contradiction',left=ep(refs[0]),right=ep(refs[1]),explanation='Несумісні передумови.')]),plan,premise,{})
    check=check_specs(repo,plan,{premise['id']:result},[premise['id']])[0]
    payload,_,_=request_for(plan,check,{premise['id']:result})
    assert len([s for s in payload['premise_authority'] if s['status']=='unresolved'])==2


def test_delta_schema_prohibits_finding_candidates(tmp_path):
    from storygen.review.wire import request_for
    repo,plan=prepare(tmp_path);spec=plan['delta_specs'][0]
    payload,body,_=request_for(plan,spec,{})
    schema=body.get('response_format',{}).get('json_schema',{}).get('schema') or payload['response_schema']
    assert schema['properties']['candidates']['maxItems']==0
