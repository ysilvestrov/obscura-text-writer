"""Synthetic qualification tests; never dispatch real models."""
import json
from pathlib import Path
from contextlib import contextmanager
import pytest
from round2b import qualification as q


def test_only_eight_old_cases_and_no_new_holdout():
    cases=q.dev_cases()
    assert len(cases)==8 and len({c['id'] for c in cases})==8
    assert sum(c['gold']['verdict']=='clean' for c in cases)==4
    assert all(not c['id'].startswith(('A1-','B1-','C1-','D1-','E1-')) for c in cases)


def test_authorization_before_io(tmp_path):
    with pytest.raises(ValueError,match='authorized'):
        q.execute(tmp_path,tmp_path,object())


def test_checksum_before_any_dispatch(tmp_path):
    with pytest.raises(ValueError,match='checksum'):
        q.verify_manifest(tmp_path,{'sha256':'bad'})


def fixture(tmp_path,monkeypatch):
    from round2.freeze import snapshot,ledger_anchor
    from round2.cloud import balance
    from round2.runner import digest,atomic_json
    cases=q.dev_cases()
    configs={k:dict(provider='local',model=k,context_tokens=32768) for k in q.LABELS}
    configs['C1']=dict(provider='google',model='gemini-3.5-flash-lite')
    configs['C2']=dict(provider='anthropic',model='claude-haiku-5-5',schema_relaxation_approved=True)
    ledger=tmp_path/'artifacts/round-2/cloud-budget.sqlite';balance(ledger)
    m=dict(original=snapshot(tmp_path,[],{}),source_inventory=[],files={},prompt='synthetic prompt',cases=cases,
           configs=configs,models={k:{'bytes':7} for k in ['L3','L5','L6']},
           profiles={k:{} for k in ['L3','L5','L6']},ledger_anchor=ledger_anchor(ledger))
    m['calls']=40;m['cloud_calls']=16;m['per_call_reserve']='0.05'
    m['contracts']={label:{c['id']:digest(q.envelope(q.ap_request(c,cfg,m['prompt'])['body'],cfg['provider'],cfg)) for c in m['cases']} for label,cfg in m['configs'].items()}
    m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});atomic_json(tmp_path/'manifest.json',m)
    monkeypatch.setattr(q,'inventory',lambda c:[]);monkeypatch.setattr(q,'verify_model_binding',lambda *a:None)
    @contextmanager
    def loaded(*args,**kwargs):yield {'instance_id':'synthetic-instance'}
    monkeypatch.setattr(q,'loaded_model',loaded)
    return m,ledger


def reply(provider):
    usage={'promptTokenCount':10,'candidatesTokenCount':2,'thoughtsTokenCount':0,'totalTokenCount':12} if provider=='google' else {'input_tokens':10,'output_tokens':2}
    return dict(status='valid',text='{"concerns":[]}',usage=usage,reasoning_tokens=0,reasoning_chars=0,seconds=1)


def test_complete_forty_and_resume_without_replay(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch);sent=[]
    def send(client,req,provider,cfg,**kwargs):sent.append(provider);return reply(provider)
    monkeypatch.setattr(q,'dispatch',send)
    result=q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(sent)==40 and sent.count('local')==24
    assert all(x['calls']==8 for x in result['counts'].values())
    assert result['holdout_allowed'] is True
    q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(sent)==40


def test_invalid_not_repaired_and_systematic_gate(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch);sent=[]
    def send(client,req,provider,cfg,**kwargs):
        sent.append(provider);r=reply(provider)
        if provider=='local':r.update(status='invalid',text='bad',rejection_codes=['invalid_json'])
        return r
    monkeypatch.setattr(q,'dispatch',send)
    result=q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(sent)==40 and result['counts']['L6']['invalid']==8
    assert not result['holdout_allowed'] and 'L6:systematic_invalid' in result['gates']


def test_unknown_reasoning_stops_and_cleans_up(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch);sent=[]
    def send(client,req,provider,cfg,**kwargs):
        sent.append(provider);r=reply(provider)
        if provider=='local':r['reasoning_tokens']=None
        return r
    monkeypatch.setattr(q,'dispatch',send)
    with pytest.raises(ValueError,match='reasoning'):
        q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert sent.count('local')==1


def test_uncertain_paid_never_replays(tmp_path,monkeypatch):
    import httpx
    fixture(tmp_path,monkeypatch);sent=[]
    def fail(*a,**kw):sent.append(1);raise httpx.ReadTimeout('secret')
    monkeypatch.setattr(q,'dispatch',fail)
    for _ in range(2):
        with pytest.raises(ValueError,match='uncertain|owner'):
            q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(sent)==1


def test_l3_slow_call_resource_gate(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch)
    def send(client,req,provider,cfg,**kwargs):
        r=reply(provider)
        if provider=='local':r['seconds']=61
        return r
    monkeypatch.setattr(q,'dispatch',send)
    with pytest.raises(ValueError,match='60'):
        q.execute(tmp_path,tmp_path,object(),authorized=True)


def test_clean_concerns_gate_uses_all_statuses():
    cases={c['id']:c for c in q.dev_cases()};clean=[c for c in cases.values() if c['gold']['verdict']=='clean']
    rows=[dict(label='L5',case=c['id'],status='invalid',text='{"concerns":[{"kind":"issue"}]}') for c in clean]
    result=q.summarize(rows,cases)
    assert 'L5:clean_concerns' in result['gates'] and not result['holdout_allowed']


def test_wire_drift_before_dispatch(tmp_path,monkeypatch):
    from round2.runner import digest,atomic_json
    m,_=fixture(tmp_path,monkeypatch)
    m['contracts']['C1'][m['cases'][0]['id']]='bad'
    m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'});atomic_json(tmp_path/'manifest.json',m)
    sent=[];monkeypatch.setattr(q,'dispatch',lambda *a,**kw:sent.append(1))
    with pytest.raises(ValueError,match='wire changed'):
        q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert not sent


def test_insufficient_full_reserve_before_any_send(tmp_path,monkeypatch):
    from round2.cloud import paid_call
    from decimal import Decimal
    _,ledger=fixture(tmp_path,monkeypatch)
    with pytest.raises(RuntimeError):
        paid_call(ledger,'held',{},Decimal('9.95'),lambda:(_ for _ in ()).throw(RuntimeError()),lambda r:None)
    sent=[];monkeypatch.setattr(q,'dispatch',lambda *a,**kw:sent.append(1))
    with pytest.raises(ValueError,match='Full outstanding dev reserve'):
        q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert not sent


def test_refusal_stops_without_further_cases(tmp_path,monkeypatch):
    fixture(tmp_path,monkeypatch);sent=[]
    def send(client,req,provider,cfg,**kwargs):
        sent.append(1);return dict(reply(provider),status='refusal')
    monkeypatch.setattr(q,'dispatch',send)
    with pytest.raises(ValueError,match='Refusal stops'):
        q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(sent)==1


def test_local_timeout_stops_once_and_never_replays(tmp_path,monkeypatch):
    import httpx
    fixture(tmp_path,monkeypatch);sent=[]
    def send(client,req,provider,cfg,**kwargs):
        sent.append(provider)
        if provider=='local':raise httpx.ReadTimeout('synthetic')
        return reply(provider)
    monkeypatch.setattr(q,'dispatch',send)
    for _ in range(2):
        with pytest.raises(ValueError,match='owner|uncertain'):
            q.execute(tmp_path,tmp_path,object(),authorized=True)
    assert sent.count('local')==1 and len(sent)==17
