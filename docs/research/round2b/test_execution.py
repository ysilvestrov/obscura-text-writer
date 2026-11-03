"""Execution boundary tests use fabricated inputs and in-memory HTTP only."""
from copy import deepcopy
import json
from pathlib import Path
import httpx
import pytest
from round2b.execution import Adapter,body_bytes
from round2b.dev import ap_request
from round2.transports import envelope
from round2.runner import digest


def adapter(tmp_path,local=False):
    cfg=dict(provider='local' if local else 'google',model='unit' if local else 'gemini-3.5-flash-lite',context_tokens=32768)
    label='L3' if local else 'C1'
    cases=[dict(id='unit-a',sources=['Ніна прочитала записку.'],target='Ніна сховала папір.'),
           dict(id='unit-b',sources=['Ніна відчинила двері.'],target='Ніна зайшла до кімнати.')]
    saved={label:{}}
    meta={label:{}}
    for c in cases:
        req=ap_request(c,cfg,'A-prime unit prompt.');wire=envelope(req['body'],cfg['provider'],cfg)
        saved[label][c['id']]=dict(request=req,wire=wire)
        meta[label][c['id']]=dict(wire_sha256=digest(wire))
    slots=[dict(config=label,case=c['id'],draw=1,block=0,phase='quality') for c in cases]
    a=Adapter(tmp_path,cases,{label:cfg},'A-prime unit prompt.',saved,meta,slots,{label:{'context_length':32768}},'input-unit')
    return a,slots


def test_canonical_bytes_have_no_nan():
    value={'б':'ї','a':1}
    assert body_bytes(value)==httpx.Request('POST','https://unit.example',json=value).content
    with pytest.raises(ValueError):body_bytes({'a':float('nan')})


def test_reordered_json_keys_are_not_the_frozen_bytes(tmp_path):
    a,slots=adapter(tmp_path);wire=deepcopy(a.saved['C1']['unit-a']['wire'])
    wire['body']=dict(reversed(list(wire['body'].items())))
    assert digest(wire)==a.contracts['C1']['unit-a']['wire_sha256']
    with pytest.raises(ValueError,match='bytes'):a.prepare(slots[0],wire=wire)


def test_exact_body_and_round2b_output(tmp_path):
    a,slots=adapter(tmp_path);p=a.prepare(slots[0])
    assert p['body']==body_bytes(a.saved['C1']['unit-a']['wire']['body'])
    assert a.guard_http(p, httpx.Request('POST',p['url'],content=p['body']))
    assert '/artifacts/round-2b/quality/' in str(a.paths(slots[0])['result']).replace('\\','/')


@pytest.mark.parametrize('mutation',['prompt','url','model','other_case'])
def test_wire_mutation_never_calls_sender(tmp_path,mutation):
    a,slots=adapter(tmp_path);w=deepcopy(a.saved['C1']['unit-a']['wire'])
    if mutation=='prompt':w['body']['systemInstruction']['parts'][0]['text']='legacy A'
    if mutation=='url':w['url']='https://invalid.example/'
    if mutation=='model':w['body']['model']='other'
    if mutation=='other_case':w=deepcopy(a.saved['C1']['unit-b']['wire'])
    with pytest.raises(ValueError):a.prepare(slots[0],wire=w)


def test_final_request_guard_reads_stream_not_only_cached_content(tmp_path):
    a,slots=adapter(tmp_path);p=a.prepare(slots[0]);request=httpx.Request('POST',p['url'],content=p['body'])
    request.stream=httpx.ByteStream(b'changed')
    with pytest.raises(ValueError,match='bytes'):a.guard_http(p,request)


def test_unknown_slot_and_path_injection(tmp_path):
    a,slots=adapter(tmp_path)
    with pytest.raises(ValueError):a.prepare(dict(slots[0],draw=99))
    with pytest.raises(ValueError):a.paths(dict(slots[0],case='../escape'))


def test_backend_echo_exact_and_no_model_substitution(tmp_path):
    a,slots=adapter(tmp_path,local=True)
    with pytest.raises(ValueError,match='backend'):a.prepare(slots[0])
    with pytest.raises(ValueError,match='profile'):a.prepare(slots[0],echo={'instance_id':'unit','load_config':{}})
    with pytest.raises(ValueError,match='model'):a.prepare(slots[0],echo={'instance_id':'unit-other','load_config':{'context_length':32768}})
    p=a.prepare(slots[0],echo={'instance_id':'unit','load_config':{'context_length':32768}})
    assert json.loads(p['body'])['model']=='unit'


def test_no_activation_means_no_http(tmp_path):
    a,slots=adapter(tmp_path);calls=[]
    with httpx.Client(transport=httpx.MockTransport(lambda req:calls.append(req))) as client:
        with pytest.raises(ValueError,match='activation'):a.send(client,slots[0],{})
    assert calls==[]


def test_dryrun_no_http_no_quality_results(tmp_path):
    a,slots=adapter(tmp_path);result=a.dry_run(tmp_path/'artifacts/round-2b/execution-dry-run')
    assert result['slots']==2 and result['http_calls']==0 and result['body_matches']==2
    assert not (tmp_path/'artifacts/round-2b/quality/slots').exists()


def test_authorized_send_uses_exact_content_bytes_and_no_logged_keys(tmp_path,monkeypatch):
    a,slots=adapter(tmp_path);a.execution_id='exec-unit'
    monkeypatch.setattr(a,'require_activation',lambda:None);monkeypatch.setattr(a,'source_guard',lambda:None)
    monkeypatch.setenv('GOOGLE_API_KEY','unit-private-key')
    from round2.cloud import balance
    balance(tmp_path/'artifacts/round-2/cloud-budget.sqlite')
    observed=[]
    def handler(req):
        observed.append(req.content)
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"complete":true,"concerns":[],"carry_refs":[]}'}]},'finishReason':'STOP'}],
            'usageMetadata':{'promptTokenCount':10,'candidatesTokenCount':2,'thoughtsTokenCount':0,'totalTokenCount':12},'modelVersion':'gemini-3.5-flash-lite'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:r=a.send(client,slots[0],{'slot':'unit'})
    assert r['status']=='valid' and observed==[a.prepare(slots[0])['body']]
    for p in (tmp_path/'artifacts/round-2b/quality/requests').glob('*'):
        assert b'unit-private-key' not in p.read_bytes()


def test_dryrun_cannot_create_http_client(tmp_path,monkeypatch):
    a,_=adapter(tmp_path)
    def forbidden(*args,**kwargs):raise AssertionError('No HTTP client in dryrun')
    monkeypatch.setattr(httpx,'Client',forbidden)
    assert a.dry_run(tmp_path/'artifacts/round-2b/isolated-dry')['http_calls']==0


def test_run_without_authorization_never_reads_credentials_or_creates_client(tmp_path,monkeypatch):
    a,_=adapter(tmp_path)
    monkeypatch.setattr(httpx,'Client',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('no client')))
    with pytest.raises(ValueError,match='authorized'):a.run(authorized=False)


def test_one_shot_stream_is_rejected_even_if_first_iteration_matches(tmp_path):
    a,slots=adapter(tmp_path);p=a.prepare(slots[0]);r=httpx.Request('POST',p['url'],content=p['body'])
    r.stream=iter([p['body']])
    with pytest.raises(ValueError,match='bytes'):a.guard_http(p,r)


def test_send_byte_mismatch_precedes_ledger_and_http(tmp_path,monkeypatch):
    a,slots=adapter(tmp_path);a.execution_id='exec-unit';original=a.prepare
    monkeypatch.setattr(a,'require_activation',lambda:None);monkeypatch.setattr(a,'source_guard',lambda:None)
    monkeypatch.setenv('GOOGLE_API_KEY','unit-key')
    def corrupt(*args,**kwargs):
        p=original(*args,**kwargs);p['body']=b'changed';return p
    monkeypatch.setattr(a,'prepare',corrupt);calls=[]
    with httpx.Client(transport=httpx.MockTransport(lambda r:calls.append(r))) as client:
        with pytest.raises(ValueError,match='bytes'):a.send(client,slots[0],{})
    assert calls==[] and not (tmp_path/'artifacts/round-2/cloud-budget.sqlite').exists()
    assert not (tmp_path/'artifacts/round-2b/quality/requests').exists()


def test_wrong_activation_freeze_is_rejected(tmp_path):
    a,_=adapter(tmp_path);a.execution_id='exec-unit';p=tmp_path/'artifacts/round-2b/quality/activation.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps(dict(execution_sha256='other',input_sha256='input-unit',owner_authorized=True,exclusive_local_api_window=True)))
    with pytest.raises(ValueError,match='activation'):a.require_activation()


def test_runtime_version_drift_stops_preflight():
    from round2b.execution import runtime_guard
    with pytest.raises(ValueError,match='runtime'):runtime_guard({'python':'not-this-version','packages':{}})


@pytest.mark.parametrize('operation',['paths','dryrun'])
def test_round2b_parent_junction_cannot_route_output_to_round2(tmp_path,operation):
    import os
    old=tmp_path/'artifacts/round-2';old.mkdir(parents=True)
    link=tmp_path/'artifacts/round-2b'
    if os.name=='nt':
        import _winapi
        _winapi.CreateJunction(str(old),str(link))
    else:link.symlink_to(old,target_is_directory=True)
    a,slots=adapter(tmp_path)
    with pytest.raises(ValueError,match='namespace'):
        if operation=='paths':a.paths(slots[0])
        else:a.dry_run(link/'execution-dry-run')
    assert not list(old.iterdir())
