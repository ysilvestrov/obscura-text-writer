"""Freeze/prepare are offline; drift and unreviewed policy fail closed."""
import copy
from pathlib import Path

import pytest


def test_snapshot_detects_content_inventory_and_metadata_drift(tmp_path):
    from .freeze import snapshot,verify_snapshot
    (tmp_path/'code.py').write_text('a=1\n')
    data=snapshot(tmp_path,['code.py'],dict(prompt='A',revision='a'*40))
    verify_snapshot(tmp_path,data,['code.py'])
    changed=copy.deepcopy(data);changed['metadata']['prompt']='C'
    with pytest.raises(ValueError,match='checksum'):verify_snapshot(tmp_path,changed,['code.py'])
    with pytest.raises(ValueError,match='inventory'):verify_snapshot(tmp_path,data,['code.py','new.py'])
    (tmp_path/'code.py').write_text('a=2\n')
    with pytest.raises(ValueError,match='drift'):verify_snapshot(tmp_path,data,['code.py'])


@pytest.mark.parametrize('name',['../outside','/absolute','.env','folder/.env','C:/secret','.ENV','.AWS/credentials'])
def test_snapshot_rejects_secret_or_escaping_paths(tmp_path,name):
    from .freeze import snapshot
    with pytest.raises(ValueError):snapshot(tmp_path,[name],{})


def test_wire_prompt_hash_uses_actual_text_not_windows_newlines(tmp_path):
    from .freeze import sent_text_hash
    p=tmp_path/'prompt.txt';p.write_bytes('Рядок1\r\nРядок2\r\n'.encode())
    q=tmp_path/'lf.txt';q.write_bytes('Рядок1\nРядок2\n'.encode())
    assert sent_text_hash(p)==sent_text_hash(q)


def test_primary_config_selection_ignores_counters_but_not_policy():
    from .freeze import primary_config
    m=dict(experiment='x',seed=1,inference_calls=112,primary_prompt={'condition':'A'},secondary_policy={'version':'v1'})
    a=primary_config(m);m['inference_calls']=999
    assert primary_config(m)==a
    m['secondary_policy']['version']='v2'
    assert primary_config(m)!=a


def test_freeze_gates_need_all_dev_and_approved_policies():
    from .freeze import check_gates
    m=dict(holdout_approved=True,weights_prepared=True,dev_qualified=True,
           primary_prompt=dict(condition='A',tuning_stopped=True),
           secondary_policy=dict(scope_approved_in_chat=True,closed_defects=['incomplete_processing','duplicate_source_reference']),
           review_policy=dict(approved=True),cloud_budget_approved=True,cloud_budget_usd='10.00')
    dev={k:dict(calls=8,reasoning_tokens_observed=[0]*8) for k in ['L1','L2','L3','L4','L5','L6','C1','C2']}
    check_gates(m,dev)
    dev['L2']['calls']=7
    with pytest.raises(ValueError,match='dev'):check_gates(m,dev)
    dev['L2']['calls']=8;m['review_policy']['approved']=False
    with pytest.raises(ValueError,match='review'):check_gates(m,dev)


def test_quality_reserve_is_shared_tariff_bound_and_expires():
    from .freeze import reserve_for_wire
    wire={'body':{'generationConfig':{'maxOutputTokens':4096},'contents':[{'parts':[{'text':'Синтетичний текст'}]}]}}
    value=reserve_for_wire('gemini-3.5-flash-lite',wire,day='2026-10-29')
    assert value>0 and value<.05
    with pytest.raises(ValueError,match='tariff'):reserve_for_wire('gemini-3.5-flash-lite',wire,day='2026-12-01')


def test_readonly_budget_does_not_create_or_reset_missing_ledger(tmp_path):
    from .freeze import readonly_budget
    path=tmp_path/'missing.sqlite'
    with pytest.raises(ValueError,match='ledger'):readonly_budget(path)
    assert not path.exists()


def test_ledger_anchor_preserves_dev_spend_and_allows_new_calls(tmp_path):
    from decimal import Decimal
    import sqlite3
    from .cloud import paid_call
    from .freeze import ledger_anchor,verify_ledger_anchor,readonly_budget
    path=tmp_path/'ledger.sqlite'
    paid_call(path,'dev-one',{},'.2',lambda:{},lambda _:Decimal('.1'))
    anchor=ledger_anchor(path)
    assert readonly_budget(path)==Decimal('9.9')
    paid_call(path,'quality-one',{},'.2',lambda:{},lambda _:Decimal('.1'))
    verify_ledger_anchor(path,anchor)
    assert readonly_budget(path)==Decimal('9.8')
    with sqlite3.connect(path) as db:db.execute('DELETE FROM calls WHERE id=?',('dev-one',))
    with pytest.raises(ValueError,match='ledger'):verify_ledger_anchor(path,anchor)


def test_wire_contract_hashes_actual_native_envelopes_without_gold():
    from .freeze import wire_contracts
    from .test_round2 import case
    c=case();c['gold']['secret']='GOLD-CANARY'
    configs={'L1':dict(provider='local',model='l1',context_tokens=131072),
             'C2':dict(provider='anthropic',model='claude-haiku-5-5',schema_relaxation_approved=True)}
    contracts=wire_contracts([c],configs)
    assert len(contracts)==2
    assert contracts['L1'][c['id']]['system_sha256']!=contracts['C2'][c['id']]['system_sha256']
    assert contracts['L1'][c['id']]['schema_sha256']!=contracts['C2'][c['id']]['schema_sha256']
    assert 'GOLD-CANARY' not in str(contracts)


def test_active_configs_are_exactly_the_eight_approved_roles():
    from .freeze import active_configs
    m={'cloud_models':{'C1':{'provider':'google','model':'gemini-3.5-flash-lite'},
                       'C2':{'provider':'anthropic','model':'claude-haiku-5-5'}}}
    cfg=active_configs(m)
    assert set(cfg)=={'L1','L2','L3','L4','L5','L6','C1','C2'}
    assert cfg['L3']['context_tokens']==32768 and cfg['L4']['context_tokens']==32768
    assert cfg['L1']['context_tokens']==131072 and cfg['C2']['schema_relaxation_approved']
    m['cloud_models']['C1']['model']='unapproved-model'
    with pytest.raises(ValueError):active_configs(m)


def test_source_inventory_ignores_results_and_catches_added_code(tmp_path):
    from .freeze import source_inventory
    for folder in ['src/storygen/generation/resources','docs/research/round2','artifacts']:
        (tmp_path/folder).mkdir(parents=True)
    (tmp_path/'src/storygen/a.py').write_text('pass')
    (tmp_path/'src/storygen/generation/resources/a.txt').write_text('prompt')
    (tmp_path/'docs/research/round2/report.json').write_text('{}')
    (tmp_path/'artifacts/ignored.py').write_text('pass')
    names=source_inventory(tmp_path)
    assert 'src/storygen/a.py' in names and not any('artifacts' in n or n.endswith('report.json') for n in names)
    (tmp_path/'docs/research/round2/new.py').write_text('pass')
    assert source_inventory(tmp_path)!=names


def test_prepare_detects_configuration_wire_and_ledger_drift(tmp_path):
    from .freeze import freeze_candidate,prepare_candidate,active_configs
    from .cloud import paid_call
    from .test_round2 import case
    from decimal import Decimal
    (tmp_path/'code.py').write_text('code')
    ledger=tmp_path/'ledger.sqlite'
    paid_call(ledger,'dev',{},'.1',lambda:{},lambda _:Decimal('.01'))
    m={'cloud_models':{'C1':{'provider':'google','model':'gemini-3.5-flash-lite'},
                       'C2':{'provider':'anthropic','model':'claude-haiku-5-5'}},'seed':17}
    cases=[case()];configs=active_configs(m)
    frozen=freeze_candidate(tmp_path,['code.py'],m,cases,configs,ledger,code_commit='a'*40,day='2026-10-29')
    result=prepare_candidate(tmp_path,['code.py'],frozen,m,cases,configs,ledger,day='2026-10-29')
    assert result['primary_slots']==24 and result['cloud_slots']==6
    assert result['inference_performed'] is False and frozen['metadata']['activated'] is False
    m['seed']=18
    with pytest.raises(ValueError,match='configuration'):prepare_candidate(tmp_path,['code.py'],frozen,m,cases,configs,ledger)
    m['seed']=17;cases[0]['target']+=' Drift'
    with pytest.raises(ValueError,match='contract'):prepare_candidate(tmp_path,['code.py'],frozen,m,cases,configs,ledger)


def test_readonly_budget_blocks_over_reserve_charges(tmp_path):
    from .cloud import paid_call
    from .freeze import readonly_budget
    from decimal import Decimal
    ledger=tmp_path/'ledger.sqlite'
    paid_call(ledger,'over',{},'.1',lambda:{},lambda _:Decimal('.2'))
    with pytest.raises(ValueError,match='reserve'):readonly_budget(ledger)


def test_model_files_detect_weight_content_and_size_drift(tmp_path):
    from .freeze import verify_model_files
    from .weights import file_hash
    p=tmp_path/'synthetic.gguf';p.write_bytes(b'weight')
    models={'L1':dict(path=str(p),bytes=6,sha256=file_hash(p))}
    verify_model_files(models)
    p.write_bytes(b'change')
    with pytest.raises(ValueError,match='weight'):verify_model_files(models)


def test_dev_evidence_rejects_saved_reply_tampering(tmp_path):
    from .freeze import audit_dev
    from .runner import atomic_json,digest
    from .dev import old_cases
    from .requests import build_request
    from .transports import envelope
    from .freeze import active_configs
    m={'cloud_models':{'C1':{'provider':'google','model':'gemini-3.5-flash-lite'},'C2':{'provider':'anthropic','model':'claude-haiku-5-5'}}}
    cfgs=active_configs(m)
    for label,cfg in cfgs.items():
        folder=tmp_path/'artifacts/round-2/dev'/label;folder.mkdir(parents=True)
        for c in old_cases():
            result=dict(status='invalid',text='bad',reasoning_tokens=0,reasoning_chars=0)
            req=build_request(c,cfg)
            if label.startswith('L'):
                (folder/'slots').mkdir(exist_ok=True)
                atomic_json(folder/'slots'/(c['id']+'.json'),dict(result=result,result_sha256=digest(result)))
                atomic_json(folder/(c['id']+'-request.json'),req['body'])
            else:
                atomic_json(folder/(c['id']+'-response.json'),result)
                atomic_json(folder/(c['id']+'-request.json'),envelope(req['body'],cfg['provider'],cfg))
    audit=audit_dev(tmp_path,cfgs)
    assert all(audit['summary'][label]['calls']==8 for label in cfgs)
    path=tmp_path/'artifacts/round-2/dev/L2/slots/nude-clean.json'
    value=json_load(path);value['result']['text']='changed'
    from .runner import atomic_json
    atomic_json(path,value)
    with pytest.raises(ValueError,match='checksum'):audit_dev(tmp_path,cfgs)


def json_load(path):
    import json
    return json.loads(path.read_text(encoding='utf-8'))


def test_activation_requires_review_of_exact_candidate():
    from .freeze import activate_candidate
    from .runner import digest
    candidate=dict(version=1,files={'x':'sha'},metadata={'activated':False})
    candidate['snapshot_sha256']=digest(candidate)
    review=dict(candidate_sha256=candidate['snapshot_sha256'],critical=0,important=0,tests_passed=True)
    active=activate_candidate(candidate,review)
    assert active['metadata']['activated'] and not candidate['metadata']['activated']
    for bad in [dict(review,important=1),dict(review,tests_passed=False),dict(review,candidate_sha256='other')]:
        with pytest.raises(ValueError):activate_candidate(candidate,bad)


def test_blinding_seed_is_private_and_commitment_bound(tmp_path):
    from .freeze import blinding_seed
    from .runner import atomic_json,digest
    policy=dict(blinding_seed_file='private.json',blind_labels_seed_sha256=digest(12345))
    atomic_json(tmp_path/'private.json',{'seed':12345})
    assert blinding_seed(tmp_path,policy)==12345
    with pytest.raises(ValueError,match='blinding'):blinding_seed(tmp_path,dict(policy,blind_labels_seed=12345))
    atomic_json(tmp_path/'private.json',{'seed':12346})
    with pytest.raises(ValueError,match='blinding'):blinding_seed(tmp_path,policy)
