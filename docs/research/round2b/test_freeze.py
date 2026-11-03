"""Freeze policy and pure native-wire tests; no real holdout or HTTP."""
import json
import pytest
from round2b.freeze import secondary_policy,admission,contracts
from round2.scoring import classify_secondary


def test_closed_secondary_scope_and_primary_unchanged():
    p=secondary_policy()
    assert set(p['closed_defects'])=={'incomplete_processing','duplicate_source_reference'}
    assert p['duplicate_scope']=='source_refs_only' and p['combinations_allowed']
    assert not p['counts_for_thresholds'] and not p['normalize_kind']
    assert p['owner_reviews_all_candidates']


def test_question_on_issue_is_semantic_even_when_complete_false():
    candidate=dict(complete=False,concerns=[dict(kind='question',message='Яке джерело обрати?',
                   change_refs=['C1'],target_refs=['T2'],source_refs=['S1'])],carry_refs=[])
    r=dict(status='invalid',secondary_eligible=True,contract_defects=['incomplete_processing'],
           secondary_candidate=candidate,text=json.dumps(candidate))
    gold=dict(verdict='issue',contradictions=[dict(id='g1')])
    judge=dict(content_refusal=False,question_ok=False,question_judgements={'0':False},matches={})
    result=classify_secondary(r,gold,judge)
    assert result['executor']['classification']['outcome']=='FN'
    assert result['executor']['classification']['fn_ids']==['g1']
    assert candidate['concerns'][0]['kind']=='question' and r['status']=='invalid'


def test_only_owner_accepted_l3_gate():
    assert admission({'complete':True,'gates':['L3:systematic_invalid']},True)['accepted']
    with pytest.raises(ValueError):admission({'complete':True,'gates':['L3:systematic_invalid']},False)
    with pytest.raises(ValueError):admission({'complete':True,'gates':['L6:systematic_invalid']},True)


def test_contracts_use_exact_aprime_without_inference():
    cases=[dict(id='unit',sources=['Ніна прочитала записку.'],target='Ніна сховала папір.')]
    cfg={'L3':dict(provider='local',model='unit',context_tokens=32768),
         'C2':dict(provider='anthropic',model='claude-haiku-5-5',schema_relaxation_approved=True)}
    saved,meta,reserves=contracts(cases,cfg,'Власний A-prime промпт.')
    assert len(saved)==len(meta)==2
    assert saved['L3']['unit']['request']['body']['messages'][0]['content']=='Власний A-prime промпт.'
    assert saved['C2']['unit']['wire']['body']['system'].startswith('Власний A-prime промпт.\n')
    assert 'Обмеження результату' in saved['C2']['unit']['wire']['body']['system']
    assert meta['C2']['unit']['schema_deviations']
    assert float(reserves['C2'])>0


@pytest.mark.parametrize('field,eligible',[('source_refs',True),('target_refs',False),('change_refs',False)])
def test_secondary_only_source_duplicates(field,eligible):
    from round2.validation import diagnose
    from round2b.dev import ap_request
    req=ap_request(dict(id='unit',sources=['Ніна біля дверей.'],target='Ніна зайшла.'),dict(model='unit',context_tokens=32768),'Промпт.')
    c=dict(kind='issue',message='Конфлікт',change_refs=['C1'],source_refs=['S1'],target_refs=['T2'])
    c[field]*=2
    result=diagnose(dict(complete=False,concerns=[c],carry_refs=[]),req)
    assert result['secondary_eligible'] is eligible


def test_existing_freeze_never_overwritten(tmp_path):
    from round2b.freeze import prepare
    p=tmp_path/'docs/research/round2b/frozen-quality.json';p.parent.mkdir(parents=True);p.write_text('original')
    with pytest.raises(ValueError,match='never overwrite'):
        prepare(tmp_path,tmp_path/'artifacts/quality',{},l3_approved=True)
    assert p.read_text()=='original'


def test_full_offline_package_has_720_slots_private_seeds_and_drift_guard(tmp_path,monkeypatch):
    from pathlib import Path
    from round2b import freeze as f
    from round2b.test_author_holdout import quartet_templates
    from round2b.author_holdout import make_cases,encoded
    from round2.cloud import balance
    folder=tmp_path/'docs/research/round2b';folder.mkdir(parents=True)
    data=make_cases(quartet_templates());(folder/'holdout-reviewed.json').write_bytes(encoded(data))
    (folder/'oracle-comparison-revision4.json').write_bytes(encoded(dict(owner_oracle_complete=True,open_disagreements=[],reviewed_holdout_sha256=f.file_sha(folder/'holdout-reviewed.json'))))
    prompt=(Path(f.__file__).parent/'prompts/check-aprime-v1-uk.txt').read_bytes()
    (folder/'prompts').mkdir();(folder/'prompts/check-aprime-v1-uk.txt').write_bytes(prompt)
    cfg={k:dict(provider='local',model=k,context_tokens=32768) for k in f.LABELS}
    cfg['C1']=dict(provider='google',model='gemini-3.5-flash-lite')
    cfg['C2']=dict(provider='anthropic',model='claude-haiku-5-5',schema_relaxation_approved=True)
    q=dict(configs=cfg,models={},profiles={},prompt=prompt.decode())
    monkeypatch.setattr(f,'qualification_evidence',lambda root:(q,dict(summary=dict(complete=True,gates=['L3:systematic_invalid'])),[]))
    monkeypatch.setattr(f.subprocess,'check_output',lambda *a,**kw:'unit-commit\n')
    for name in ['docs/research/2026-10-30-round2b-freeze-admission.md','docs/research/2026-10-29-round-2-prompt-freeze-amendment.md',
                 'docs/research/round2b/qualification-results.json','docs/research/round2b/qualification-content-review.json']:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
    balance(tmp_path/'artifacts/round-2/cloud-budget.sqlite')
    output=tmp_path/'artifacts/round-2b/quality'
    package=f.prepare(tmp_path,output,{'observed':'synthetic'},l3_approved=True)
    assert f.verify(tmp_path,package)
    assert package['metadata']['slots']==720 and not package['metadata']['quality_authorized']
    schedule=json.loads((output/'schedule.json').read_text())
    assert len(schedule)==720 and all('seed' not in s for s in schedule)
    for seed in json.loads((output/'private-seeds.json').read_text()).values():
        assert str(seed) not in json.dumps(package)
    (folder/'holdout-reviewed.json').write_text('changed')
    with pytest.raises(ValueError,match='drift'):f.verify(tmp_path,package)


def test_external_binary_change_is_detected(tmp_path):
    from round2b.freeze import verify_external
    from round2b.spike import file_sha
    p=tmp_path/'engine.dll';p.write_bytes(b'first')
    records={'engine':dict(path=str(p),sha256=file_sha(p),bytes=5)}
    verify_external(records)
    p.write_bytes(b'other')
    with pytest.raises(ValueError,match='External file drift'):verify_external(records)


def test_saved_summary_cannot_hide_unapproved_gate():
    from round2b.freeze import verify_dev_summary
    rows=[dict(label='L6',case='unit',status='invalid',text='{}') for _ in range(2)]
    cases={'unit':dict(gold=dict(verdict='clean'))}
    with pytest.raises(ValueError,match='summary'):
        verify_dev_summary(rows,cases,dict(complete=True,gates=[]))


def test_verify_rejects_missing_frozen_ledger(tmp_path):
    from round2b.freeze import verify,secondary_policy
    from round2.freeze import snapshot,ledger_anchor
    from round2.cloud import balance
    p=tmp_path/'artifacts/round-2/cloud-budget.sqlite';balance(p)
    metadata=dict(source_inventory=[],quality_authorized=False,activated=False,
                  admission=dict(secondary=secondary_policy()),models={},environment={},
                  ledger=ledger_anchor(p),cloud_total_reserve='0.10')
    package=snapshot(tmp_path,[],metadata);p.unlink()
    with pytest.raises(ValueError,match='ledger'):verify(tmp_path,package)
