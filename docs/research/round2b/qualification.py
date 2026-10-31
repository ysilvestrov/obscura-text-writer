"""Old-dev qualification only: eight published cases, never the new holdout."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

from round2.dev import old_cases
from round2.freeze import (source_inventory, verify_snapshot, reserve_for_wire,
                          readonly_budget, ledger_anchor, verify_ledger_anchor)
from round2.runner import digest, atomic_json, run_slot
from round2.transports import envelope, dispatch
from round2.cloud import paid_call, usage_cost
from round2.local_models import inventory, loaded_model
from round2b.spike import file_sha, verify_model_binding
from round2b.dev import ap_request, content_counts, LABELS

PROMPT_SHA='55fe4d840642b93c69d01d1b2a4d5d421282b99e51bf6ac054d27028593a9088'


def dev_cases():
    # Deliberately no corpus-loader argument: requests can only use round-one dev.
    return [dict(c,gold=dict(verdict='issue' if c['expected_issue'] else 'clean')) for c in old_cases()]


def verify_manifest(root,m):
    root=Path(root)
    if digest({k:v for k,v in m.items() if k!='sha256'})!=m.get('sha256'):
        raise ValueError('Qualification manifest checksum changed')
    verify_snapshot(root,m['original'],list(m['original']['files']))
    if source_inventory(root)!=m['source_inventory']:raise ValueError('Qualification source inventory changed')
    for path,sha in m['files'].items():
        if file_sha(root/path)!=sha:raise ValueError('Qualification file drift: '+path)
    verify_ledger_anchor(root/'artifacts/round-2/cloud-budget.sqlite',m['ledger_anchor'])


def prepare(root,folder):
    root=Path(root);folder=Path(folder)
    if (folder/'manifest.json').exists():raise ValueError('Qualification already prepared; never overwrite')
    read=lambda name:json.loads((root/name).read_text(encoding='utf-8'))
    original=read('docs/research/round2/frozen-primary.json')
    verify_snapshot(root,original,list(original['files']))
    completion=read('docs/research/round2b/oracle-comparison-revision4.json')
    if (completion.get('owner_oracle_complete') is not True or completion.get('open_disagreements')
            or completion.get('verdict_agreement')!=[48,48]):raise ValueError('Oracle incomplete')
    for name,key in [('holdout-reviewed.json','reviewed_holdout_sha256'),('oracle-blind-v4-annotated.md','owner_panel_sha256')]:
        if file_sha(root/'docs/research/round2b'/name)!=completion[key]:raise ValueError('Oracle source drift')
    promptpath=root/'docs/research/round2b/prompts/check-aprime-v1-uk.txt'
    if file_sha(promptpath)!=PROMPT_SHA:raise ValueError('Approved prompt drift')
    prompt=promptpath.read_text(encoding='utf-8');cases=dev_cases()
    if len(cases)!=8 or sum(c['gold']['verdict']=='clean' for c in cases)!=4:raise ValueError('Old dev changed')
    configs={label:deepcopy(original['metadata']['configs'][label]) for label in LABELS}
    registry=read('artifacts/round-2/preflight/model-links.json');models={}
    for label in ['L3','L5','L6']:
        model=deepcopy(original['metadata']['models'][label]);path=Path(model['path'])
        if not path.is_file() or file_sha(path)!=model['sha256']:raise ValueError('Weight SHA changed: '+label)
        models[label]=dict(model,key=configs[label]['model'],registered_path=registry['links'].get(label,model['path']),
                           publisher='round2-r28l' if label in registry['links'] else path.parts[path.parts.index('models')+1])
    source=source_inventory(root)
    expected={'docs/research/round2b/'+name+'.py' for name in ['spike','test_spike','dev','test_dev','author_holdout','test_author_holdout','qualification','test_qualification']}
    expected|={'docs/research/r28m-spike.py','docs/research/r28n-aprime-dev.py','docs/research/r28o-round2b-qualification.py'}
    if set(source)-set(original['files'])!=expected:raise ValueError('Unexpected source additions')
    files=expected|{'docs/research/round2b/prompts/check-aprime-v1-uk.txt',
        'docs/research/round2b/oracle-comparison-revision4.json','docs/research/round2b/holdout-reviewed.json',
        'docs/research/round2b/oracle-blind-v4-annotated.md',
        'docs/superpowers/plans/2026-10-30-round2b-dev-freeze.md',
        'docs/research/2026-10-29-round-2b-holdout-rebuild-plan.md','artifacts/round-2/preflight/model-links.json'}
    contracts={};reserves={}
    for label,cfg in configs.items():
        contracts[label]={};amount=Decimal(0)
        for case in cases:
            wire=envelope(ap_request(case,cfg,prompt)['body'],cfg['provider'],cfg)
            contracts[label][case['id']]=digest(wire)
            if cfg['provider']!='local':
                reserve=reserve_for_wire(cfg['model'],wire)
                if reserve>Decimal('0.05'):raise ValueError('Dev call exceeds approved reserve ceiling')
                amount+=reserve
        if cfg['provider']!='local':reserves[label]=str(amount)
    ledger=root/'artifacts/round-2/cloud-budget.sqlite'
    verify_ledger_anchor(ledger,original['metadata']['ledger'])
    anchor=ledger_anchor(ledger);available=readonly_budget(ledger);total=sum(map(Decimal,reserves.values()))
    if total>available or total>Decimal('0.80'):raise ValueError('Full dev reserve exceeds budget')
    m=dict(stage='round2b-qualification-v1',original=original,cases=cases,configs=configs,models=models,prompt=prompt,
        prompt_sha256=PROMPT_SHA,source_inventory=source,files={p:file_sha(root/p) for p in sorted(files)},
        contracts=contracts,profiles={label:original['metadata']['native_load_profiles'][label] for label in models},
        ledger_anchor=anchor,reserves=reserves,total_reserve=str(total),available_before=str(available),
        calls=40,cloud_calls=16,per_call_reserve='0.05',systematic_invalid_threshold=2,
        gates_policy='Complete old dev without repairs; >=2/8 invalid or >=3/4 clean concerns gates holdout. Resource/reasoning/refusal stops immediately.',
        oracle='complete; reviewed holdout hashes checked only, never used in dev requests')
    m['sha256']=digest(m);folder.mkdir(parents=True,exist_ok=True);atomic_json(folder/'manifest.json',m)
    return m


def summarize(rows,cases):
    counts={label:content_counts([r for r in rows if r['label']==label],cases) for label in LABELS}
    gates=[]
    for label,count in counts.items():
        if count['invalid']>=2:gates.append(label+':systematic_invalid')
        if count['clean_with_concerns']>=3:gates.append(label+':clean_concerns')
        if count['refusal']:gates.append(label+':refusal')
    complete=all(c['calls']==8 for c in counts.values())
    return dict(counts=counts,gates=gates,complete=complete,holdout_allowed=complete and not gates,
                quality_authorized=False)


def execute(root,folder,client,*,authorized=False):
    if not authorized:raise ValueError('Qualification dev not authorized')
    root=Path(root);folder=Path(folder);m=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));verify_manifest(root,m)
    from contextlib import nullcontext
    from decimal import Decimal
    outstanding=Decimal(0)
    for label in LABELS:
        cfg=m['configs'][label]
        for case in m['cases']:
            req=ap_request(case,cfg,m['prompt']);wire=envelope(req['body'],cfg['provider'],cfg)
            identity=dict(iteration=m['sha256'],label=label,case=case['id'],wire=digest(wire))
            path=folder/'slots'/f'{label}-{case["id"]}.json'
            if path.exists():
                state=json.loads(path.read_text(encoding='utf-8'))
                if state['identity']!=digest(identity):raise ValueError('Dev checkpoint identity changed')
                if state.get('blocked') or state.get('inflight'):raise ValueError('Previous dev call uncertain; owner decision required')
                if 'result' in state:
                    if state.get('result_sha256')!=digest(state['result']):raise ValueError('Dev result checksum changed')
                    if cfg['provider']!='local':
                        import sqlite3
                        ledger=root/'artifacts/round-2/cloud-budget.sqlite'
                        with sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True) as db:
                            paid=db.execute('SELECT identity,result FROM calls WHERE id=?',(f'round2b-qualification-v1-{label}-{case["id"]}',)).fetchone()
                        if not paid or paid[0]!=digest(identity) or paid[1] is None or json.loads(paid[1])!=state['result']:
                            raise ValueError('Completed paid checkpoint missing from ledger; reconcile before resume')
                    continue
            if cfg['provider']!='local':
                reserve=reserve_for_wire(cfg['model'],wire)
                if reserve>Decimal(m['per_call_reserve']):raise ValueError('Dev call exceeds reserve ceiling')
                outstanding+=reserve
    if outstanding>readonly_budget(root/'artifacts/round-2/cloud-budget.sqlite'):
        raise ValueError('Full outstanding dev reserve exceeds shared budget')
    if any(r.get('loaded_instances') for r in inventory(client)):raise ValueError('GPU busy; coordinate first')
    (folder/'requests').mkdir(exist_ok=True);rows=[];cases={c['id']:c for c in m['cases']}
    for label in LABELS:
        cfg=m['configs'][label];local=cfg['provider']=='local'
        def checkpoint(case):return folder/'slots'/f'{label}-{case["id"]}.json'
        needed=any(not checkpoint(c).exists() or 'result' not in json.loads(checkpoint(c).read_text(encoding='utf-8')) for c in m['cases'])
        if local and needed:verify_model_binding(m['models'][label],inventory(client))
        context=loaded_model(client,cfg['model'],cfg['context_tokens'],expected_profile=m['profiles'][label],expected_size=m['models'][label]['bytes']) if local and needed else nullcontext({})
        with context as loaded:
            epoch=len(list(folder.glob(f'load-{label}-session*.json')))+1;loadpath=folder/f'load-{label}-session{epoch}.json'
            if local and needed:atomic_json(loadpath,loaded)
            for case in m['cases']:
                verify_manifest(root,m);req=ap_request(case,cfg,m['prompt']);wire=envelope(req['body'],cfg['provider'],cfg)
                if digest(wire)!=m['contracts'][label][case['id']]:raise ValueError('Dev wire changed')
                identity=dict(iteration=m['sha256'],label=label,case=case['id'],wire=digest(wire))
                def send():
                    if local:
                        instance=loaded.get('instance_id') or loaded.get('model_instance_id');dcfg=dict(cfg,model=instance)
                        atomic_json(folder/'requests'/f'{label}-{case["id"]}.json',dict(envelope(req['body'],'local',dcfg),canonical_wire_sha256=digest(wire),load_session=loadpath.name))
                        return dispatch(client,req,'local',dcfg,authorized=True)
                    atomic_json(folder/'requests'/f'{label}-{case["id"]}.json',wire)
                    ledger=root/'artifacts/round-2/cloud-budget.sqlite';reserve=reserve_for_wire(cfg['model'],wire)
                    available=readonly_budget(ledger)  # Before paid_call durably subtracts this reserve.
                    return paid_call(ledger,f'round2b-qualification-v1-{label}-{case["id"]}',identity,reserve,
                        lambda:dispatch(client,req,cfg['provider'],cfg,authorized=True,reserve=reserve,available=available),
                        lambda result:usage_cost(cfg['model'],result.get('usage')))
                result=run_slot(folder/'slots',f'{label}-{case["id"]}',identity,send,authorized=True,retry_transport=False)
                rows.append(dict(result,label=label,case=case['id']))
                counts={k:content_counts([r for r in rows if r['label']==k],cases) for k in LABELS}
                atomic_json(folder/'progress.json',dict(completed=len(rows),total=40,label=label,last=case['id'],counts=counts))
                print(json.dumps(dict(completed=len(rows),label=label,case=case['id'],status=result['status'],seconds=result.get('seconds')),ensure_ascii=False),flush=True)
                if result['status']=='refusal':raise ValueError('Refusal stops qualification; owner review required')
                if local and label=='L3' and result.get('seconds',0)>60:raise ValueError('L3 short call exceeds60seconds')
                if local and (result.get('reasoning_tokens')!=0 or result.get('reasoning_chars')!=0):raise ValueError('Local reasoning not proven off')
    summary=summarize(rows,cases)
    atomic_json(folder/'summary.json',summary)
    return summary
