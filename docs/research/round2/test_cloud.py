"""Offline cloud amendment, accounting and native Google contracts."""
import json
from decimal import Decimal

import httpx
import pytest

from .test_round2 import prepared, raw


def test_google_native_schema_and_default_thinking(monkeypatch):
    from .transports import dispatch, envelope
    req=prepared();config=dict(model='gemini-3.5-flash-lite',key_env='TEST_GOOGLE')
    wire=envelope(req['body'],'google',config)
    assert wire['url'].endswith('/models/gemini-3.5-flash-lite:generateContent')
    assert wire['body']['generationConfig']==dict(maxOutputTokens=4096,responseMimeType='application/json',
        responseJsonSchema=req['body']['response_format']['json_schema']['schema'])
    assert wire['body']['systemInstruction']['parts'][0]['text']==req['body']['messages'][0]['content']
    assert 'gold' not in json.dumps(wire['body'])
    monkeypatch.setenv('TEST_GOOGLE','SECRET-CANARY')
    def handler(r):
        assert r.headers['x-goog-api-key']=='SECRET-CANARY'
        assert 'SECRET-CANARY' not in str(r.url) and b'SECRET-CANARY' not in r.content
        return httpx.Response(200,json=dict(candidates=[dict(content=dict(parts=[dict(text='hidden',thought=True),
            dict(text=json.dumps(raw()))]),finishReason='STOP')],usageMetadata=dict(promptTokenCount=100,
            candidatesTokenCount=30,thoughtsTokenCount=12),modelVersion='pinned-version'))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=dispatch(client,req,'google',config,authorized=True,reserve='.1',available='1')
    assert result['status']=='valid' and result['reasoning_tokens']==12 and result['reasoning_chars']==6
    assert result['provider_model']=='pinned-version' and 'SECRET-CANARY' not in json.dumps(result)


@pytest.mark.parametrize('payload,finish,refusal',[
    (dict(promptFeedback=dict(blockReason='SAFETY')),'refusal',True),
    (dict(candidates=[dict(finishReason='MAX_TOKENS',content=dict(parts=[]))]),'length',False),
    (dict(candidates=[dict(finishReason='SAFETY',content=dict(parts=[]))]),'refusal',True),
])
def test_google_refusal_and_truncation(payload,finish,refusal):
    from .transports import normalize
    result=normalize(payload,'google')
    assert result['finish_reason']==finish and result['refusal']==refusal
    assert result['reasoning_tokens'] is None


def test_google_rejects_malformed_parts():
    from .transports import normalize
    with pytest.raises(ValueError):normalize(dict(candidates=[dict(content=dict(parts=['bad']))]),'google')


def test_shared_budget_persists_across_models_and_reuses_completed_call(tmp_path):
    from .cloud import paid_call, balance
    db=tmp_path/'budget.sqlite';calls=[]
    def send():calls.append(1);return dict(status='valid',usage={})
    assert paid_call(db,'C1-dev-1',{'model':'C1'},'6',send,lambda _:Decimal('4'))['status']=='valid'
    assert balance(db)==Decimal('6')
    paid_call(db,'C1-dev-1',{'model':'C1'},'6',lambda:pytest.fail('duplicate'),lambda _:None)
    with pytest.raises(ValueError,match='budget'):
        paid_call(db,'C2-dev-1',{'model':'C2'},'6.01',send,lambda _:None)
    assert len(calls)==1
    paid_call(db,'C2-dev-1',{'model':'C2'},'6',send,lambda _:None)
    assert balance(db)==0


def test_uncertain_paid_call_keeps_reserve_and_cannot_replay(tmp_path):
    from .cloud import paid_call, balance
    db=tmp_path/'budget.sqlite'
    def send():raise httpx.ReadError('do not persist secret exception text')
    with pytest.raises(httpx.ReadError):paid_call(db,'C1-1',{},'2',send,lambda _:None)
    assert balance(db)==8
    with pytest.raises(ValueError,match='uncertain'):
        paid_call(db,'C1-1',{},'2',lambda:pytest.fail('duplicate'),lambda _:None)
    assert b'secret exception' not in db.read_bytes()


def test_budget_identity_change_and_invalid_money_are_rejected(tmp_path):
    from .cloud import paid_call
    db=tmp_path/'budget.sqlite'
    paid_call(db,'one',{'model':'one'},'1',lambda:{},lambda _:None)
    with pytest.raises(ValueError,match='identity'):
        paid_call(db,'one',{'model':'two'},'1',lambda:pytest.fail('sent'),lambda _:None)
    for reserve in ['NaN','Infinity','-1','0']:
        with pytest.raises(ValueError):paid_call(db,'new',{},reserve,lambda:pytest.fail('sent'),lambda _:None)


def test_usage_cost_google_includes_reasoning_and_anthropic_does_not_double_count():
    from .cloud import usage_cost
    assert usage_cost('gemini-3.5-flash-lite',dict(promptTokenCount=1000,candidatesTokenCount=100,
        thoughtsTokenCount=200),day='2026-10-29')==Decimal('.00105')
    assert usage_cost('claude-haiku-5-5',dict(input_tokens=1000,output_tokens=300),day='2026-10-29')==Decimal('.00025')
    assert usage_cost('claude-haiku-5-5',dict(input_tokens=100001,output_tokens=1000),day='2026-10-29')==Decimal('.0525005')
    assert usage_cost('gemini-4-argon',{},day='2026-10-29') is None
    assert usage_cost('gemini-4-argon',dict(promptTokenCount=True,candidatesTokenCount=2,thoughtsTokenCount=0),day='2026-10-29') is None
    with pytest.raises(ValueError,match='tariff'):
        usage_cost('gemini-4-argon',{},day='2026-12-01')


def test_google_total_usage_can_settle_cost_without_inventing_reasoning_telemetry(tmp_path):
    from .cloud import usage_cost, paid_call, settle_saved, balance
    usage=dict(promptTokenCount=615,candidatesTokenCount=40,totalTokenCount=655)
    assert usage_cost('gemini-3.5-flash-lite',usage,day='2026-10-29')==Decimal('.0002845')
    db=tmp_path/'budget.sqlite'
    paid_call(db,'one',{},'.05',lambda:dict(usage=usage),lambda _:None)
    assert balance(db)==Decimal('9.95')
    settle_saved(db,'one',lambda result:usage_cost('gemini-3.5-flash-lite',result['usage'],day='2026-10-29'))
    assert balance(db)==Decimal('9.9997155')


def test_provider_exceeding_reserved_cost_blocks_followup_calls(tmp_path):
    from .cloud import paid_call
    db=tmp_path/'budget.sqlite'
    paid_call(db,'one',{},'.01',lambda:{},lambda _:Decimal('.02'))
    with pytest.raises(ValueError,match='reserve'):
        paid_call(db,'two',{},'.01',lambda:pytest.fail('sent'),lambda _:None)


def test_escalation_uses_union_of_failed_templates_with_full_quartets():
    from .cloud import escalation_cases
    cases=[dict(id=f'{t}-{v}-{c}',template=t) for t in ['A1','B1'] for v in ['a','b'] for c in ['neutral','adult']]
    rows=[dict(config='C1',case='A1-a-neutral',failed=True),dict(config='C2',case='A1-b-adult',failed=True),
          dict(config='L1',case='B1-a-neutral',failed=True)]
    assert escalation_cases(cases,rows)==[c['id'] for c in cases if c['template']=='A1']
    with pytest.raises(ValueError):escalation_cases(cases,[dict(config='C1',case='missing',failed=True)])
