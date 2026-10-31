"""A-prime tuning uses only old dev and four permanently excluded D controls."""
from pathlib import Path
import json
import pytest

from round2b.dev import dev_cases,ap_request,content_counts,verify_manifest

ROOT=Path(__file__).resolve().parents[3]

def test_dev_is_forty_old_non_d_plus_four_new_d():
    cases=dev_cases(ROOT)
    assert len(cases)==44 and len({c['id'] for c in cases})==44
    old=[c for c in cases if not c.get('dev_only')]
    new=[c for c in cases if c.get('dev_only')]
    assert len(old)==40 and all(c['family']!='D' for c in old)
    assert len(new)==4 and all(c['exclude_from_holdout_2b'] for c in new)
    assert sorted(c['gold']['verdict'] for c in new)==['clean','clean','question','question']
    for theme in ['time','injury']:
        pair=[c for c in new if c['theme']==theme]
        assert pair[0]['target']==pair[1]['target']
        a=next(c for c in pair if c['gold']['verdict']=='question')
        b=next(c for c in pair if c['gold']['verdict']=='clean')
        assert b['sources'][:-1]==a['sources']
        assert 'Автор' not in a['target'] and 'Автор' in b['sources'][-1]

def test_aprime_only_replaces_system_not_schema_or_payload():
    from round2.requests import build_request
    cfg=dict(model='l3',context_tokens=32768)
    case=dev_cases(ROOT)[0];prompt='A-prime candidate'
    before=build_request(case,cfg);after=ap_request(case,cfg,prompt)
    assert after['body']['messages'][0]['content']==after['plan']['system']==prompt
    assert before['payload']==after['payload']
    assert before['body']['response_format']==after['body']['response_format']
    assert before['body']['messages'][1:]==after['body']['messages'][1:]
    assert after['plan']['result_cap']==4096

def test_content_counts_do_not_equate_validity_with_quality():
    cases={c['id']:c for c in dev_cases(ROOT)}
    clean=next(c for c in cases.values() if c['gold']['verdict']=='clean')
    question=next(c for c in cases.values() if c['gold']['verdict']=='question')
    rows=[dict(case=clean['id'],status='valid',text='{"concerns":[{"kind":"issue"}]}'),
          dict(case=question['id'],status='valid',text='{"concerns":[{"kind":"issue"}]}')]
    counts=content_counts(rows,cases)
    assert counts['valid']==2 and counts['clean_with_concerns']==1
    assert counts['question_as_issue']==1 and counts['question_empty']==0

def test_manifest_tampering_rejected_before_files_or_dispatch(tmp_path):
    with pytest.raises(ValueError,match='checksum'):verify_manifest(tmp_path,{'sha256':'bad'})

def make_manifest(tmp_path):
    from round2.freeze import snapshot,ledger_anchor
    from round2.runner import digest,atomic_json
    from round2.transports import envelope
    from round2.cloud import balance
    from round2b.dev import LABELS
    cases=dev_cases(ROOT)
    configs={k:dict(provider='local',model=k,context_tokens=32768) for k in LABELS}
    configs['C1']=dict(provider='google',model='gemini-3.5-flash-lite')
    configs['C2']=dict(provider='anthropic',model='claude-haiku-5-5',schema_relaxation_approved=True)
    m=dict(original=snapshot(tmp_path,[],{}),source_inventory=[],files={},prompt='candidate',cases=cases,configs=configs,
           models={k:{'bytes':7} for k in ['L3','L5','L6']},profiles={k:{} for k in ['L3','L5','L6']},
           contracts={k:{c['id']:digest(envelope(ap_request(c,cfg,'candidate')['body'],cfg['provider'],cfg)) for c in cases} for k,cfg in configs.items()})
    ledger=tmp_path/'artifacts/round-2/cloud-budget.sqlite';balance(ledger)
    m['ledger_anchor']=ledger_anchor(ledger)
    m['sha256']=digest(m);atomic_json(tmp_path/'manifest.json',m)
    return m,ledger

def test_dev_authorization_precedes_io(tmp_path):
    from round2b.dev import execute
    with pytest.raises(ValueError,match='authorized'):execute(tmp_path,tmp_path,object())

def test_complete_dev_resume_preserves_paid_budget_and_skips_inference(tmp_path,monkeypatch):
    from contextlib import contextmanager
    import round2b.dev as d
    from round2.freeze import readonly_budget
    make_manifest(tmp_path);sent=[];unloaded=[]
    monkeypatch.setattr(d,'inventory',lambda c:[]);monkeypatch.setattr(d,'verify_model_binding',lambda *args:None)
    @contextmanager
    def loaded(client,key,*args,**kwargs):
        try:yield {'instance_id':key}
        finally:unloaded.append(key)
    monkeypatch.setattr(d,'loaded_model',loaded)
    def dispatch(client,req,provider,cfg,**kwargs):
        sent.append(provider)
        if provider!='local':
            assert kwargs['available']==readonly_budget(tmp_path/'artifacts/round-2/cloud-budget.sqlite')+kwargs['reserve']
        usage={'promptTokenCount':10,'candidatesTokenCount':2,'thoughtsTokenCount':0,'totalTokenCount':12} if provider=='google' else {'input_tokens':10,'output_tokens':2}
        return dict(status='valid',text='{"concerns":[]}',usage=usage,reasoning_tokens=0,reasoning_chars=0)
    monkeypatch.setattr(d,'dispatch',dispatch)
    result=d.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(sent)==220 and sent.count('local')==132 and len(unloaded)==3
    before=readonly_budget(tmp_path/'artifacts/round-2/cloud-budget.sqlite')
    d.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(sent)==220 and len(unloaded)==3
    assert readonly_budget(tmp_path/'artifacts/round-2/cloud-budget.sqlite')==before
    assert all(v['calls']==44 for v in result.values())
    import sqlite3
    ledger=tmp_path/'artifacts/round-2/cloud-budget.sqlite'
    with sqlite3.connect(ledger) as db:db.execute("DELETE FROM calls WHERE id=(SELECT id FROM calls ORDER BY id LIMIT 1)")
    with pytest.raises(ValueError,match='checkpoint missing from ledger'):
        d.execute(tmp_path,tmp_path,object(),authorized=True)
    assert len(sent)==220

def test_uncertain_cloud_does_not_repeat_or_log_exception_text(tmp_path,monkeypatch):
    import httpx
    import round2b.dev as d
    make_manifest(tmp_path);sent=[]
    monkeypatch.setattr(d,'inventory',lambda c:[])
    def fail(*args,**kwargs):sent.append(1);raise httpx.ReadTimeout('secret-must-not-be-logged')
    monkeypatch.setattr(d,'dispatch',fail)
    for _ in range(2):
        with pytest.raises(ValueError,match='uncertain|requires owner'):d.execute(tmp_path,tmp_path,object(),authorized=True)
    assert sent==[1]
    assert 'secret-must-not-be-logged' not in next((tmp_path/'slots').glob('*.json')).read_text()

def test_full_outstanding_series_reserve_is_checked_before_send(tmp_path,monkeypatch):
    from decimal import Decimal
    from round2.cloud import paid_call
    import round2b.dev as d
    _,ledger=make_manifest(tmp_path);sent=[]
    def uncertain():raise RuntimeError('synthetic')
    with pytest.raises(RuntimeError):paid_call(ledger,'held',{},Decimal('9.95'),uncertain,lambda r:None)
    monkeypatch.setattr(d,'inventory',lambda c:[])
    monkeypatch.setattr(d,'dispatch',lambda *args,**kwargs:sent.append(1))
    with pytest.raises(ValueError,match='Full outstanding dev reserve'):d.execute(tmp_path,tmp_path,object(),authorized=True)
    assert sent==[]

def test_malformed_invalid_concerns_do_not_block_reporting_or_resume():
    cases={c['id']:c for c in dev_cases(ROOT)}
    case=next(c for c in cases.values() if c['gold']['verdict']=='question')
    rows=[dict(case=case['id'],status='invalid',text=json.dumps({'concerns':value}))
          for value in [[None],1,[{'kind':[]}]]]
    counts=content_counts(rows,cases)
    assert counts['invalid']==3 and counts['question_calls']==3
    assert counts['question_unreadable']==3 and counts['question_only']==0

def test_saved_ledger_anchor_rejects_reset_even_with_same_limit(tmp_path):
    import sqlite3
    from decimal import Decimal
    from round2.cloud import paid_call
    from round2.freeze import ledger_anchor
    from round2.runner import digest
    m,ledger=make_manifest(tmp_path)
    paid_call(ledger,'baseline',{},Decimal('0.5'),lambda:{'ok':True},lambda r:Decimal('0.1'))
    m['ledger_anchor']=ledger_anchor(ledger);m['sha256']=digest({k:v for k,v in m.items() if k!='sha256'})
    with sqlite3.connect(ledger) as db:db.execute('DELETE FROM calls WHERE id=?',('baseline',))
    with pytest.raises(ValueError,match='ledger reset'):verify_manifest(tmp_path,m)
