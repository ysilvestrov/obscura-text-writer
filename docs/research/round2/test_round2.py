"""Offline contract tests. No inference, no environment keys, no product data."""
import copy
import json
import socket

import httpx
import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('Network forbidden during round2 self-check')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket, 'create_connection', denied)


def case(verdict='issue', count=1):
    return dict(id='A1-neutral-b', template='A1', family='A', variant='b', context='neutral',
                ages=[], sources=['Подія почалася о 14:00.'], target='Ця подія почалася о 11:00.',
                gold=dict(verdict=verdict, clean_reason='Сумісно.' if verdict=='clean' else '',
                          contradictions=[dict(id=f'g{i}', source_indices=[0], target_quote='11:00',
                                               type='time', severity='major') for i in range(count)] if verdict=='issue' else [],
                          question_reason='Недостатньо даних.' if verdict=='question' else ''))


def prepared():
    from .requests import build_request
    return build_request(case(), dict(model='synthetic-local'))


def raw(concerns=(), complete=True):
    return dict(complete=complete, concerns=list(concerns), carry_refs=[])


def concern(request, message='Суперечність часу.', kind='issue'):
    evidence=request['payload']['evidence']
    return dict(kind=kind, message=message, change_refs=[],
                source_refs=[next(k for k,v in evidence.items() if v['kind']=='source')],
                target_refs=[next(k for k,v in evidence.items() if v['kind']=='target')])


def response(request, concerns=(), **kwargs):
    from .scoring import validate_response
    return validate_response(dict(text=json.dumps(raw(concerns), ensure_ascii=False),
                                  finish_reason='stop', refusal=False, usage={}, **kwargs), request)


def test_three_concerns_schema():
    from .scoring import validate_response
    req=prepared()
    assert req['body']['response_format']['json_schema']['schema']['properties']['concerns']['maxItems']==3
    rows=[concern(req, f'Зауваження {i}.') for i in range(3)]
    assert validate_response(dict(text=json.dumps(raw(rows)), finish_reason='stop'),req)['status']=='valid'
    assert validate_response(dict(text=json.dumps(raw(rows+[concern(req,'Четверте.')])),finish_reason='stop'),req)['status']=='invalid'


def test_gold_not_in_request():
    from .requests import build_request
    row=case();row['gold']['private_canary']='DO_NOT_SEND_GOLD'
    req=build_request(row,dict(model='synthetic-local'))
    assert 'DO_NOT_SEND_GOLD' not in json.dumps(req['body'])
    assert row['id'] not in json.dumps(req['body'])
    assert req['body']['reasoning_effort']=='none'
    assert req['body']['max_tokens']==4096 and req['body']['temperature']==0.1
    assert req['payload']['review_basis'] and req['spec']['phase']=='check'


@pytest.mark.parametrize('finish,text', [('length','{}'),('stop',''),('stop','not json'),('stop','{"complete":false,"concerns":[],"carry_refs":[]}')])
def test_invalid_not_repaired(finish,text):
    from .scoring import validate_response
    assert validate_response(dict(text=text,finish_reason=finish),prepared())['status']=='invalid'


def test_wrong_refs_and_types_rejected():
    from .scoring import validate_response
    req=prepared();row=concern(req);row['source_refs']=['S999']
    assert validate_response(dict(text=json.dumps(raw([row])),finish_reason='stop'),req)['status']=='invalid'
    assert validate_response(dict(text=json.dumps(raw(complete='true')),finish_reason='stop'),req)['status']=='invalid'


@pytest.mark.parametrize('verdict,rows,expected', [('clean',0,'TN'),('clean',1,'FP'),('issue',0,'FN'),('issue',1,'TP'),('question',0,'question-missed'),('question',1,'question-ok')])
def test_outcome_partition(verdict,rows,expected):
    from .scoring import classify_call
    req=prepared();items=[concern(req,kind='question' if verdict=='question' else 'issue')] if rows else []
    adjudication=dict(content_refusal=False, matches={'0':['g0']} if verdict=='issue' and rows else {},
                      question_ok=verdict=='question' and bool(rows))
    result=classify_call(response(req,items),case(verdict)['gold'],adjudication)
    assert result['outcome']==expected and not result['pending']


def test_partial_e_finding():
    from .scoring import classify_call
    req=prepared();result=classify_call(response(req,[concern(req)]),case(count=2)['gold'],
        dict(content_refusal=False,matches={'0':['g0']},question_ok=False))
    assert result['outcome']=='TP' and result['tp_ids']==['g0'] and result['fn_ids']==['g1']


def test_duplicate_finding_not_double_tp():
    from .scoring import classify_call
    req=prepared();result=classify_call(response(req,[concern(req),concern(req,'Те саме.')]),case()['gold'],
        dict(content_refusal=False,matches={'0':['g0'],'1':['g0']},question_ok=False))
    assert result['tp_ids']==['g0'] and result['duplicate_findings']==1


def test_wrong_explanation_not_auto_tp():
    from .scoring import classify_call
    req=prepared();res=response(req,[concern(req)])
    pending=classify_call(res,case()['gold'],None)
    assert pending['pending'] and pending['outcome'] is None
    judged=classify_call(res,case()['gold'],dict(content_refusal=False,matches={},question_ok=False))
    assert judged['outcome']=='FN' and judged['extra_findings']==1


def test_content_refusal_inside_concerns():
    from .scoring import classify_call
    req=prepared();res=response(req,[concern(req,'Не можу аналізувати цей контент.',kind='question')])
    assert classify_call(res,case()['gold'],dict(content_refusal=True,matches={},question_ok=False))['outcome']=='refusal'


def test_missing_reasoning_is_unknown():
    from .transports import normalize
    result=normalize(dict(choices=[dict(finish_reason='stop',message=dict(content='{}'))],usage={}), 'local')
    assert result['reasoning_tokens'] is None
    assert normalize(dict(choices=[dict(finish_reason='stop',message=dict(content='{}'))],
        usage=dict(completion_tokens_details=dict(reasoning_tokens=0))), 'local')['reasoning_tokens']==0


def test_native_anthropic_payload():
    from .transports import envelope
    req=prepared();wire=envelope(req['body'],'anthropic',dict(model='synthetic-claude',schema_relaxation_approved=True))
    assert wire['url']=='https://api.anthropic.com/v1/messages'
    assert wire['body']['system'].startswith(req['body']['messages'][0]['content'])
    assert wire['body']['output_config']['format']['type']=='json_schema'
    assert 'reasoning_effort' not in wire['body'] and 'thinking' not in wire['body']
    assert 'maxItems' not in json.dumps(wire['body']['output_config']['format']['schema'])
    assert 'maxItems' in wire['body']['system']  # restrictions retained as explicit text
    assert wire['schema_deviations']


def test_anthropic_relaxation_requires_approval():
    from .transports import envelope
    with pytest.raises(ValueError,match='schema'):
        envelope(prepared()['body'],'anthropic',dict(model='synthetic-claude'))


def test_anthropic_usage_is_not_reasoning_usage():
    from .transports import normalize
    result=normalize(dict(stop_reason='end_turn',content=[dict(type='text',text='{}')],usage=dict(output_tokens=42)),'anthropic')
    assert result['reasoning_tokens'] is None and result['finish_reason']=='stop'
    assert result['provider_finish_reason']=='end_turn'


def test_schedule_balances_and_rotates():
    from .runner import make_schedule
    ids=[f'case-{i}' for i in range(48)];configs=[f'L{i}' for i in range(1,7)]
    schedule=make_schedule(ids,configs,20261028,3)
    assert len(schedule)==864 and len({(r['config'],r['case'],r['draw']) for r in schedule})==864
    assert schedule==make_schedule(ids,configs,20261028,3)
    assert schedule!=make_schedule(ids,configs,42,3)
    assert [schedule[i]['config'] for i in [0,8,16,24,32,40]]==configs
    assert schedule[48]['config']=='L2'


@pytest.mark.parametrize('status',['invalid','refusal','valid'])
def test_content_result_not_retried(tmp_path,status):
    from .runner import run_slot
    calls=[]
    def send():calls.append(1);return dict(status=status)
    result=run_slot(tmp_path,'slot',dict(prompt='hash'),send,authorized=True)
    assert result['status']==status and len(calls)==1
    assert run_slot(tmp_path,'slot',dict(prompt='hash'),send,authorized=True)==result and len(calls)==1


def test_transport_attempt_logged(tmp_path):
    from .runner import run_slot
    calls=[]
    def send():
        calls.append(1)
        if len(calls)==1:raise httpx.ReadTimeout('secret-url?key=CANARY')
        return dict(status='valid')
    assert run_slot(tmp_path,'slot',{},send,authorized=True)['status']=='valid'
    attempts=json.loads((tmp_path/'slot.json').read_text())['attempts']
    assert [r['status'] for r in attempts]==['transport','valid']
    assert 'CANARY' not in (tmp_path/'slot.json').read_text()


def test_hash_mismatch_blocks_resume(tmp_path):
    from .runner import run_slot
    run_slot(tmp_path,'slot',{'a':1},lambda:dict(status='valid'),authorized=True)
    with pytest.raises(ValueError,match='identity'):
        run_slot(tmp_path,'slot',{'a':2},lambda:pytest.fail('called'),authorized=True)


def test_inflight_not_automatically_retried(tmp_path):
    from .runner import run_slot
    def crash():raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):run_slot(tmp_path,'slot',{},crash,authorized=True)
    with pytest.raises(ValueError,match='uncertain'):
        run_slot(tmp_path,'slot',{},lambda:pytest.fail('called'),authorized=True)


def test_budget_stops_before_dispatch(tmp_path):
    from .runner import run_slot
    with pytest.raises(ValueError,match='budget'):
        run_slot(tmp_path,'slot',{},lambda:pytest.fail('called'),authorized=True,reserve=0.2,available=0.1)
    with pytest.raises(ValueError,match='authorized'):
        run_slot(tmp_path,'slot',{},lambda:pytest.fail('called'))


def test_restore_on_failure():
    from .runner import model_session
    restored=[]
    with pytest.raises(RuntimeError):
        with model_session(lambda:dict(model='original'),lambda s:restored.append(s)):
            raise RuntimeError('failure')
    assert restored==[dict(model='original')]


def test_holdout_counts():
    from .dataset import validate_dataset
    cases=[]
    for family,n in [('A',3),('B',3),('C',2),('D',2),('E',2)]:
        for i in range(1,n+1):
            for context in ['neutral','adult']:
                for variant in ['a','b']:
                    verdict=('question' if variant=='a' else 'clean') if family=='D' else 'issue' if family=='E' or variant=='b' else 'clean'
                    row=case(verdict,2 if family=='E' and variant=='a' else 1)
                    row.update(id=f'{family}{i}-{context}-{variant}',template=f'{family}{i}',family=family,context=context,variant=variant,ages=[28,32] if context=='adult' else [])
                    if context=='adult':row['sources'][0]='Учасникам 28 і 32 роки. '+row['sources'][0]
                    cases.append(row)
    counts=validate_dataset(cases)
    assert counts==dict(total=48,clean=20,issue=24,question=4,contradictions=28,adult=24,neutral=24)
    broken=copy.deepcopy(cases);broken[0]['id']=broken[1]['id']
    with pytest.raises(ValueError):validate_dataset(broken)


def test_constant_baselines():
    from .scoring import baseline
    assert baseline(case('clean')['gold'],'always-issue')['outcome']=='FP'
    assert baseline(case(count=2)['gold'],'always-clean')['fn_ids']==['g0','g1']


def test_final_report_requires_adjudication():
    from .report import metrics
    with pytest.raises(ValueError,match='pending'):metrics([dict(pending=True)])


def test_metrics_retains_invalid_in_denominators():
    from .report import metrics
    from .scoring import classify_call
    rows=[classify_call({'status':'invalid'},case(count=2)['gold'],None),
          classify_call({'status':'refusal'},case('clean')['gold'],None)]
    result=metrics(rows)
    assert result['total']==2 and result['clean_denominator']==1 and result['issue_denominator']==2
    assert result['miss']==2 and result['valid']==0


def test_explicit_refusal_not_retried(tmp_path):
    from .runner import run_slot
    calls=[]
    def send():calls.append(1);return dict(status='refusal')
    assert run_slot(tmp_path,'refusal',{},send,authorized=True)['status']=='refusal'
    assert len(calls)==1


def test_checkpoint_tamper_detected(tmp_path):
    from .runner import run_slot
    run_slot(tmp_path,'slot',{},lambda:dict(status='valid'),authorized=True)
    path=tmp_path/'slot.json';state=json.loads(path.read_text());state['result']['status']='invalid'
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError,match='checksum'):
        run_slot(tmp_path,'slot',{},lambda:pytest.fail('called'),authorized=True)


def test_http_dispatch_requires_authorization_and_budget(monkeypatch):
    from .transports import dispatch
    req=prepared()
    def handler(request):pytest.fail('Unauthorized HTTP dispatch')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='authorized'):dispatch(client,req,'openai',dict(model='synthetic-cloud'))
        with pytest.raises(ValueError,match='budget'):
            dispatch(client,req,'openai',dict(model='synthetic-cloud'),authorized=True)


def test_native_anthropic_dispatch_uses_header_not_body(monkeypatch):
    from .transports import dispatch
    monkeypatch.setenv('ROUND2_TEST_KEY','SECRET-CANARY')
    def handler(request):
        assert request.url.path=='/v1/messages'
        assert request.headers['x-api-key']=='SECRET-CANARY'
        assert request.headers['anthropic-version']=='2023-06-01'
        assert b'SECRET-CANARY' not in request.content
        return httpx.Response(200,json=dict(stop_reason='end_turn',content=[dict(type='text',text=json.dumps(raw()))],usage={}))
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=dispatch(client,prepared(),'anthropic',dict(model='synthetic-claude',key_env='ROUND2_TEST_KEY',schema_relaxation_approved=True),
                        authorized=True,reserve=0.05,available=0.1)
    assert result['status']=='valid' and result['reasoning_tokens'] is None
    assert 'SECRET-CANARY' not in json.dumps(result)


def test_http_error_does_not_retry_or_leak_key(monkeypatch):
    from .transports import dispatch
    monkeypatch.setenv('ROUND2_TEST_KEY','SECRET-CANARY');calls=[]
    def handler(request):calls.append(1);return httpx.Response(401,text='SECRET-CANARY')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError,match='HTTP 401') as error:
            dispatch(client,prepared(),'openai',dict(model='synthetic-cloud',key_env='ROUND2_TEST_KEY'),authorized=True,reserve=0.05,available=0.1)
    assert len(calls)==1 and 'SECRET-CANARY' not in str(error.value)


@pytest.mark.parametrize('payload',[[],None,42,{'usage':[]}, {'choices':[{'message':[]}]}])
def test_malformed_envelope_becomes_terminal_invalid(tmp_path,payload):
    from .runner import run_slot
    from .transports import dispatch
    def handler(request):return httpx.Response(200,json=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=run_slot(tmp_path,'malformed',{},lambda:dispatch(client,prepared(),'local',dict(model='synthetic'),authorized=True),authorized=True)
    state=json.loads((tmp_path/'malformed.json').read_text())
    assert result['status']=='invalid' and not state['inflight']
    assert state['attempts'][0]['status']=='invalid' and len(state['attempts'])==1


def test_extra_question_requires_own_judgement():
    from .scoring import classify_call
    req=prepared();res=response(req,[concern(req),concern(req,'Чи справді це потрібно?',kind='question')])
    judgement=dict(content_refusal=False,matches={'0':['g0']},question_ok=False)
    assert classify_call(res,case()['gold'],judgement)['pending']
    judged=classify_call(res,case()['gold'],dict(judgement,question_judgements={'1':False}))
    assert judged['outcome']=='TP' and judged['extra_findings']==1 and judged['extra_questions']==1
    justified=classify_call(res,case()['gold'],dict(judgement,question_judgements={'1':True}))
    assert justified['extra_findings']==0 and justified['questions']==1


def test_human_can_label_unstructured_content_refusal():
    from .scoring import classify_call
    result=classify_call(dict(status='invalid',text='Не можу аналізувати такий контент.'),case()['gold'],
                         dict(content_refusal=True,matches={},question_ok=False))
    assert result['outcome']=='refusal' and not result['valid']


def test_malformed_success_preserves_raw_body_usage_and_model():
    from .transports import dispatch
    import base64
    payload={'model':'synthetic','choices':'wrong','usage':{'prompt_tokens':12,'completion_tokens':3}}
    def handler(_):return httpx.Response(200,json=payload)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=dispatch(client,prepared(),'local',dict(model='synthetic'),authorized=True)
    assert result['status']=='invalid' and result['raw_response']==payload
    assert result['usage']==payload['usage'] and result['provider_model']=='synthetic'
    assert json.loads(base64.b64decode(result['raw_body_base64']))==payload


def test_non_json_success_preserves_body_without_content_retry():
    from .transports import dispatch
    from .runner import run_slot
    import base64
    calls=[]
    def handler(_):calls.append(1);return httpx.Response(200,content=b'not-json')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=dispatch(client,prepared(),'local',dict(model='synthetic'),authorized=True)
    assert len(calls)==1 and result['status']=='invalid'
    assert base64.b64decode(result['raw_body_base64'])==b'not-json'
