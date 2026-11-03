"""No live inference: frozen dispatch, safe resume and lifecycle tests."""
from contextlib import contextmanager
import json

import httpx
import pytest


def test_paid_transport_uncertainty_stops_after_one_attempt(tmp_path):
    from .runner import run_slot
    calls=[]
    def send():
        calls.append(1);raise httpx.ReadTimeout('SECRET-CANARY')
    with pytest.raises(ValueError):
        run_slot(tmp_path,'paid',{},send,authorized=True,retry_transport=False)
    assert len(calls)==1
    state=json.loads((tmp_path/'paid.json').read_text())
    assert state['blocked'] and not state['inflight']
    assert 'SECRET-CANARY' not in str(state)
    with pytest.raises(ValueError):run_slot(tmp_path,'paid',{},send,authorized=True,retry_transport=False)
    assert len(calls)==1


def test_quality_rotation_resume_and_invalid_no_retry(tmp_path):
    from .experiment import execute_schedule
    schedule=[dict(case='x',config=c,draw=1,block=0) for c in ['L1','C1']]
    configs={'L1':dict(provider='local'),'C1':dict(provider='google')}
    calls=[];life=[];guards=[]
    @contextmanager
    def session(label,config):
        life.append(('load',label))
        try:yield {'load':'synthetic'}
        finally:life.append(('unload',label))
    def send(slot,identity):
        calls.append(slot);return dict(status='invalid',text='bad',reasoning_tokens=0,reasoning_chars=0)
    def guard():guards.append(1)
    result=execute_schedule(tmp_path,schedule,configs,'frozen-id',send,session,guard,authorized=True)
    assert result['completed']==2 and len(calls)==2
    execute_schedule(tmp_path,schedule,configs,'frozen-id',send,session,guard,authorized=True)
    assert len(calls)==2 and life==[('load','L1'),('unload','L1')]
    assert len(guards)>=4


def test_quality_drift_never_dispatches_and_reasoning_leak_is_retained(tmp_path):
    from .experiment import execute_schedule
    from contextlib import nullcontext
    schedule=[dict(case='x',config='L1',draw=1,block=0)]
    configs={'L1':dict(provider='local')};calls=[]
    def guard():raise ValueError('drift')
    with pytest.raises(ValueError,match='drift'):
        execute_schedule(tmp_path,schedule,configs,'id',lambda *_:calls.append(1),lambda *_:nullcontext({}),guard,authorized=True)
    assert not calls
    def send(*_):return dict(status='valid',text='{}',reasoning_tokens=1,reasoning_chars=4)
    with pytest.raises(ValueError,match='reasoning'):
        execute_schedule(tmp_path,schedule,configs,'id',send,lambda *_:nullcontext({}),lambda:None,authorized=True)
    assert len(list((tmp_path/'slots').glob('*.json')))==1


def test_frozen_send_checks_wire_before_network(tmp_path):
    from .experiment import frozen_send
    from .requests import build_request
    from .freeze import wire_contracts
    from .test_round2 import case
    cases={case()['id']:case()};cfgs={'L1':dict(provider='local',model='synthetic')}
    contract=wire_contracts(list(cases.values()),cfgs);calls=[]
    def handler(_):calls.append(1);return httpx.Response(200,json={})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        send=frozen_send(client,tmp_path,cases,cfgs,contract,gpu=lambda:'synthetic GPU')
        cases[case()['id']]['target']+=' changed'
        with pytest.raises(ValueError,match='wire'):send(dict(case=case()['id'],config='L1',draw=1,block=0),{})
    assert not calls


def test_timing_has_separate_warmup_and_eight_measured_calls_each():
    from .experiment import timing_schedule,slot_id
    from .dev import old_cases
    configs={'L1':dict(provider='local'),'C1':dict(provider='google'),'L3':dict(provider='local')}
    schedule=timing_schedule(old_cases(),configs)
    assert len(schedule)==18 and sum(s.get('warmup',False) for s in schedule)==2
    assert all(s['phase']=='timing' and s['config']!='C1' for s in schedule)
    assert len({slot_id(s) for s in schedule})==18


def test_resumed_timing_gets_new_warmup_after_loading(tmp_path):
    from .experiment import execute_schedule,timing_schedule,slot_id
    from .runner import run_slot
    from .dev import old_cases
    from contextlib import nullcontext
    cfgs={'L1':dict(provider='local')};schedule=timing_schedule(old_cases(),cfgs)
    warmup=schedule[0]
    identity=dict(phase='timing',freeze='id',slot=warmup,config=cfgs['L1'])
    result=dict(status='valid',reasoning_tokens=0,reasoning_chars=0)
    run_slot(tmp_path/'slots',slot_id(warmup),identity,lambda:result,authorized=True)
    sent=[]
    def send(slot,_):sent.append(slot);return result
    execute_schedule(tmp_path,schedule,cfgs,'id',send,lambda *_:nullcontext({}),lambda:None,authorized=True)
    assert len(sent)==9 and sent[0].get('warmup') is True
    assert slot_id(sent[0])!=slot_id(warmup)


def test_frozen_local_dispatch_uses_verified_loaded_instance(tmp_path):
    from .experiment import frozen_send
    from .freeze import wire_contracts
    from .test_round2 import case,raw
    c=case();cfg={'L1':dict(provider='local',model='l1')};sent=[]
    def handler(request):
        sent.append(json.loads(request.content)['model'])
        return httpx.Response(200,json=dict(model='owned-instance',choices=[dict(finish_reason='stop',message={'content':json.dumps(raw())})],
            usage=dict(completion_tokens_details={'reasoning_tokens':0})))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        send=frozen_send(client,tmp_path,{c['id']:c},cfg,wire_contracts([c],cfg),gpu=lambda:'gpu',instances={'L1':'owned-instance'})
        send(dict(case=c['id'],config='L1',draw=1,block=0),{})
    assert sent==['owned-instance']
