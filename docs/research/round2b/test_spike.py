"""Offline checks for the explicitly authorized 64-call local diagnostic."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from round2b.spike import build_pair, clean_cases, schema_diff, schedule, summarize, check_request_hash, verify_guard

ROOT = Path(__file__).resolve().parents[3]

def corpus():
    return json.loads((ROOT/'docs/research/round2/holdout.json').read_text(encoding='utf-8'))

def test_only_sixteen_clean_without_d():
    cases=clean_cases(corpus())
    assert len(cases)==16
    assert all(c['gold']['verdict']=='clean' and c['family']!='D' for c in cases)

def test_schema_pair_changes_only_concerns_count():
    for case in clean_cases(corpus()):
        one,three=build_pair(case,'l1')
        s=lambda r:r['body']['response_format']['json_schema']['schema']
        assert schema_diff(s(one),s(three))==['/properties/concerns/maxItems']
        assert s(one)['properties']['concerns']['maxItems']==1
        assert s(three)['properties']['concerns']['maxItems']==3
        assert one['payload']==three['payload']
        assert one['payload']['response_character_limit']==4096
        assert one['body']['messages']==three['body']['messages']
        assert one['body']['max_tokens']==three['body']['max_tokens']==4096
        assert 'minItems' not in s(one)['properties']['concerns']

def test_diff_detects_other_schema_change():
    a={'properties':{'concerns':{'maxItems':1}},'limit':400}
    b=deepcopy(a);b['properties']['concerns']['maxItems']=3;b['limit']=200
    assert schema_diff(a,b)==['/limit','/properties/concerns/maxItems']

def test_schedule_is_balanced_reproducible_and_rotates():
    ids=[c['id'] for c in clean_cases(corpus())]
    a=schedule(ids)
    assert a==schedule(ids) and len(a)==64
    assert len({(r['case'],r['cell']) for r in a})==64
    assert {r['cell'] for r in a}=={'own3','own1','unsloth3','unsloth1'}
    assert [a[i]['cell'] for i in [0,8,16,24]]==['own3','own1','unsloth3','unsloth1']
    assert a[32]['cell']=='own1'

def test_summary_keeps_invalid_and_does_not_turn_it_into_tn():
    rows=[dict(cell='own3',status='invalid',text='{"concerns":[{}]}'),
          dict(cell='own3',status='valid',text='{"concerns":[]}'),
          dict(cell='own3',status='valid',text='{"concerns":[{}]}')]
    s=summarize(rows)['cells']['own3']
    assert s['fp']==1 and s['invalid']==1 and s['tn']==1 and s['nonempty_including_invalid']==2
    assert s['calls']==3

def test_direction_and_threshold_are_predeclared():
    def rows(counts):
        return [dict(cell=cell,status='valid',text=json.dumps({'concerns':[{}] if i<n else []}))
                for cell,n in counts.items() for i in range(16)]
    assert summarize(rows(dict(own3=16,own1=9,unsloth3=15,unsloth1=8)))['schema_effect'] is True
    assert summarize(rows(dict(own3=16,own1=9,unsloth3=8,unsloth1=15)))['schema_effect'] is False
    assert summarize(rows(dict(own3=16,own1=10,unsloth3=16,unsloth1=10)))['schema_effect'] is False
    assert summarize(rows(dict(own3=16,own1=15,unsloth3=8,unsloth1=7)))['weight_effect'] is True

def test_request_drift_stops():
    req=build_pair(clean_cases(corpus())[0],'l1')[0]
    with pytest.raises(ValueError,match='wire'):
        check_request_hash(req,'0'*64)

def test_guard_requires_original_files_and_rejects_new_unlisted_code(tmp_path):
    from round2.freeze import snapshot
    p=tmp_path/'old.py';p.write_text('x=1')
    original=snapshot(tmp_path,['old.py'],{})
    new=tmp_path/'new.py';new.write_text('y=1')
    manifest={'original':original,'extra_files':{'new.py':__import__('hashlib').sha256(new.read_bytes()).hexdigest()},'source_inventory':[]}
    verify_guard(tmp_path,manifest,inventory=lambda root:[])
    p.write_text('x=2')
    with pytest.raises(ValueError,match='drift'):verify_guard(tmp_path,manifest,inventory=lambda root:[])
    p.write_text('x=1')
    with pytest.raises(ValueError,match='inventory'):verify_guard(tmp_path,manifest,inventory=lambda root:['surprise.py'])

def test_execution_requires_authorization_before_any_api(tmp_path):
    from round2b.spike import execute
    with pytest.raises(ValueError,match='authorized'):execute(tmp_path,tmp_path,object())

def fake_manifest(tmp_path):
    from round2.freeze import snapshot
    from round2b.spike import file_sha
    from round2.runner import digest,atomic_json
    w=tmp_path/'weights.gguf';w.write_bytes(b'weights')
    cases=clean_cases(corpus());models={kind:dict(key=kind,path=str(w),registered_path=str(w),publisher='test',bytes=7,sha256=file_sha(w)) for kind in ['own','unsloth']}
    contracts={cell:{c['id']:dict(wire_sha256=digest(build_pair(c,models['own' if cell.startswith('own') else 'unsloth']['key'])[0 if cell.endswith('1') else 1]['body'])) for c in cases} for cell in ['own3','own1','unsloth3','unsloth1']}
    m=dict(original=snapshot(tmp_path,[],{}),source_inventory=[],extra_files={},models=models,cases=cases,
           schedule=schedule([c['id'] for c in cases]),contracts=contracts,profile={})
    m['sha256']=digest(m);atomic_json(tmp_path/'manifest.json',m)
    return m

def test_execution_resume_skips_completed_and_retains_invalid(tmp_path,monkeypatch):
    from contextlib import contextmanager
    import round2b.spike as s
    fake_manifest(tmp_path);calls=[];unloaded=[]
    monkeypatch.setattr(s,'inventory',lambda c:[dict(key=k,publisher='test',size_bytes=7,loaded_instances=[]) for k in ['own','unsloth']])
    @contextmanager
    def loaded(*args,**kwargs):
        try:yield {'instance_id':'owned'}
        finally:unloaded.append(True)
    monkeypatch.setattr(s,'loaded_model',loaded)
    def send(*args,**kwargs):
        calls.append(1)
        return dict(status='invalid' if len(calls)==1 else 'valid',text='{"concerns":[]}',reasoning_tokens=0,reasoning_chars=0)
    monkeypatch.setattr(s,'dispatch',send)
    first=s.execute(tmp_path,tmp_path,object(),authorized=True,max_groups=1)
    assert len(calls)==8 and first['cells']['own3']['invalid']==1 and unloaded==[True]
    second=s.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(calls)==64 and second['complete'] and second['cells']['own3']['invalid']==1
    s.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(calls)==64

def test_execution_failure_unloads_and_keeps_uncertain_slot(tmp_path,monkeypatch):
    from contextlib import contextmanager
    import round2b.spike as s
    fake_manifest(tmp_path);unloaded=[]
    monkeypatch.setattr(s,'inventory',lambda c:[dict(key=k,publisher='test',size_bytes=7,loaded_instances=[]) for k in ['own','unsloth']])
    @contextmanager
    def loaded(*args,**kwargs):
        try:yield {'instance_id':'owned'}
        finally:unloaded.append(True)
    monkeypatch.setattr(s,'loaded_model',loaded)
    def send(*args,**kwargs):raise RuntimeError('synthetic interruption')
    monkeypatch.setattr(s,'dispatch',send)
    with pytest.raises(RuntimeError):s.execute(tmp_path,tmp_path,object(),authorized=True)
    assert unloaded==[True]
    state=json.loads(next((tmp_path/'slots').glob('*.json')).read_text())
    assert state['inflight'] is True and 'result' not in state

def test_binding_rejects_same_size_replaced_registered_file(tmp_path):
    from round2b.spike import verify_model_binding,file_sha
    source=tmp_path/'source.gguf';source.write_bytes(b'weights')
    replaced=tmp_path/'registered.gguf';replaced.write_bytes(b'changed')
    model=dict(key='test',publisher='p',path=str(source),registered_path=str(replaced),bytes=7,sha256=file_sha(source))
    with pytest.raises(ValueError,match='binding'):
        verify_model_binding(model,[dict(key='test',publisher='p',size_bytes=7)])
    model['registered_path']=str(source)
    verify_model_binding(model,[dict(key='test',publisher='p',size_bytes=7)])
    with pytest.raises(ValueError,match='catalogue'):
        verify_model_binding(model,[dict(key='test',publisher='other',size_bytes=7)])

def test_resumed_group_preserves_load_evidence(tmp_path,monkeypatch):
    from contextlib import contextmanager
    import round2b.spike as s
    fake_manifest(tmp_path);calls=[];sessions=[]
    monkeypatch.setattr(s,'inventory',lambda c:[dict(key=k,publisher='test',size_bytes=7,loaded_instances=[]) for k in ['own','unsloth']])
    @contextmanager
    def loaded(*args,**kwargs):
        sessions.append(len(sessions)+1);yield {'instance_id':f'owned-{sessions[-1]}'}
    monkeypatch.setattr(s,'loaded_model',loaded)
    def send(*args,**kwargs):
        calls.append(1)
        return dict(status='valid',text='{"concerns":[]}',reasoning_tokens=0,reasoning_chars=0)
    monkeypatch.setattr(s,'dispatch',send)
    s.execute(tmp_path,tmp_path,object(),authorized=True,max_groups=1)
    first=next(tmp_path.glob('load-b0-own3*.json'));original=first.read_bytes()
    # Reconstruct a clean transport-boundary pause by removing one completed
    # checkpoint in this synthetic fixture; production evidence is never removed.
    slot=next((tmp_path/'slots').glob('*.json'));slot.unlink()
    s.execute(tmp_path,tmp_path,object(),authorized=True,max_groups=1)
    assert first.read_bytes()==original
    assert len(list(tmp_path.glob('load-b0-own3*-session*.json')))==2

def test_anchor_gates_interpretation_before_participant_rulings():
    def rows(alpha):
        return [dict(cell=cell,status='valid',text=json.dumps({'concerns':[{}] if i<n else []}))
                for cell,n in dict(own3=alpha,own1=0,unsloth3=14,unsloth1=0).items() for i in range(16)]
    low=summarize(rows(13))
    assert low['anchor_passed'] is False and low['anchor_minimum']==14
    assert low['schema_difference_meets_threshold'] is True
    assert low['schema_effect'] is False and low['participant_ruling_allowed'] is False
    high=summarize(rows(14))
    assert high['anchor_passed'] and high['schema_effect'] and high['participant_ruling_allowed']

def test_profile_adapter_changes_load_only_and_preserves_common_template():
    from round2b.spike import ProfileClient
    sent=[]
    class Client:
        def post(self,url,**kwargs):sent.append((url,kwargs));return 'response'
        def get(self,*args,**kwargs):return 'inventory'
    profile={'speculative_draft_mtp':False,'prompt_template':{'type':'jinja','template':'common'}}
    c=ProfileClient(Client(),profile)
    c.post('http://localhost:1235/api/v1/models/load',json={'model':'test'})
    assert sent[-1][1]['json']['speculative_draft_mtp'] is False
    assert sent[-1][1]['json']['prompt_template']==profile['prompt_template']
    c.post('http://localhost:1235/api/v1/models/unload',json={'instance_id':'owned'})
    assert sent[-1][1]['json']=={'instance_id':'owned'}
    assert c.get('inventory')=='inventory'
