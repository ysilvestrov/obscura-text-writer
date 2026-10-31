"""Provider and attempt failures retain safe reason codes without secret text."""
import json

import httpx
import pytest

from .test_round2 import prepared


def test_malformed_provider_reply_has_rejection_code():
    from .transports import dispatch
    with httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=[]))) as client:
        result=dispatch(client,prepared(),'local',dict(model='synthetic'),authorized=True)
    assert result['rejection_codes']==['malformed_provider_envelope'] and not result['secondary_eligible']


def test_attempt_records_transport_and_content_reason_codes(tmp_path):
    from .runner import run_slot
    calls=[]
    def send():
        calls.append(1)
        if len(calls)==1:raise httpx.ReadError('SECRET-CANARY')
        return dict(status='invalid',rejection_codes=['incomplete_processing'])
    run_slot(tmp_path,'one',{},send,authorized=True)
    state=json.loads((tmp_path/'one.json').read_text())
    assert [a['rejection_codes'] for a in state['attempts']]==[['transport_error'],['incomplete_processing']]
    assert 'SECRET-CANARY' not in json.dumps(state)


def test_http_error_is_coded_and_resume_does_not_silently_retry(tmp_path):
    from .runner import run_slot
    from .transports import dispatch
    calls=[]
    def handler(_):calls.append(1);return httpx.Response(503,text='SECRET-CANARY')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        send=lambda:dispatch(client,prepared(),'local',dict(model='synthetic'),authorized=True)
        with pytest.raises(ValueError,match='HTTP'):run_slot(tmp_path,'one',{},send,authorized=True)
        with pytest.raises(ValueError,match='HTTP'):run_slot(tmp_path,'one',{},send,authorized=True)
    state=json.loads((tmp_path/'one.json').read_text())
    assert len(calls)==1 and not state['inflight'] and state['blocked']
    assert state['attempts'][0]['rejection_codes']==['provider_http_error']
    assert state['attempts'][0]['http_status']==503
    assert 'SECRET-CANARY' not in json.dumps(state)
