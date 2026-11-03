"""Offline quality-input freeze. No HTTP, model loading, dispatch or activation."""
from collections import Counter
from decimal import Decimal
import json
import hashlib
import importlib.metadata
from pathlib import Path
import platform
import secrets
import sqlite3
import subprocess

from round2.freeze import (snapshot,verify_snapshot,source_inventory,native_parts,
                          reserve_for_wire,readonly_budget,ledger_anchor,verify_ledger_anchor)
from round2.runner import digest,make_schedule
from round2.scoring import validate_response
from round2.transports import envelope
from round2b.qualification import ap_request,LABELS,PROMPT_SHA,summarize
from round2b.author_holdout import validate_structure
from round2b.spike import file_sha

ADDED_SOURCES={'docs/research/round2b/freeze.py','docs/research/round2b/test_freeze.py',
               'docs/research/r28p-round2b-freeze.py'}


def secondary_policy():
    return dict(closed_defects=['incomplete_processing','duplicate_source_reference'],
        duplicate_scope='source_refs_only',combinations_allowed=True,all_other_validation_must_pass=True,
        normalize_kind=False,counts_for_thresholds=False,primary_invalid_unchanged=True,
        category_error_on_unambiguous_issue='semantic FN/extra-question; never repair kind',
        owner_reviews_all_candidates=True,executor_judgements='provisional',use='descriptive only')


def admission(summary,l3_approved):
    if not summary.get('complete'):raise ValueError('Dev incomplete')
    gates=set(summary.get('gates',[]))
    if gates-{'L3:systematic_invalid'} or ('L3:systematic_invalid' in gates and not l3_approved):
        raise ValueError('Unapproved qualification gate')
    return dict(accepted=True,owner_approved_l3=l3_approved,observed_gates=sorted(gates),
        l3_expectation=dict(source='owner decision2026-10-30 before holdout',
            expected_primary_valid_threshold_failure=True,anticipated_cause='complete=false',
            prediction_not_observed_result=True),secondary=secondary_policy())


def contracts(cases,configs,prompt):
    saved={};meta={};reserves={}
    for label,cfg in configs.items():
        saved[label]={};meta[label]={};total=Decimal(0)
        for case in cases:
            request=ap_request(case,cfg,prompt);wire=envelope(request['body'],cfg['provider'],cfg)
            system,schema=native_parts(wire,cfg['provider'])
            size=len(json.dumps(wire['body'],ensure_ascii=False,separators=(',',':')).encode())
            if cfg['provider']=='local' and size+8192+4096>cfg['context_tokens']:
                raise ValueError('Local conservative context bound exceeded')
            if cfg['provider']!='local':total+=3*reserve_for_wire(cfg['model'],wire)
            saved[label][case['id']]=dict(request=request,wire=wire)
            meta[label][case['id']]=dict(wire_sha256=digest(wire),schema_sha256=digest(schema),
                system_sha256=hashlib.sha256(system.encode()).hexdigest(),
                schema_deviations=wire['schema_deviations'],input_wire_bytes=size)
        if cfg['provider']!='local':reserves[label]=str(total)
    return saved,meta,reserves


def qualification_evidence(root):
    root=Path(root);folder=root/'artifacts/round-2b/qualification'
    read=lambda path:json.loads(path.read_text(encoding='utf-8'))
    q=read(folder/'manifest.json');audit=read(folder/'audit.json')
    if digest({k:v for k,v in q.items() if k!='sha256'})!=q['sha256']:raise ValueError('Dev manifest checksum')
    if audit['manifest_sha256']!=q['sha256']:raise ValueError('Wrong dev audit')
    if read(root/'docs/research/round2b/qualification-preflight.json')['sha256']!=q['sha256']:
        raise ValueError('Dev identity differs from pre-inference record')
    verify_snapshot(root,q['original'],list(q['original']['files']))
    if set(source_inventory(root))!=set(q['source_inventory'])|ADDED_SOURCES:
        raise ValueError('Unexpected source inventory beyond declared freeze additions')
    for name,sha in q['files'].items():
        if file_sha(root/name)!=sha:raise ValueError('Original qualification source drift: '+name)
    if q['configs']!={label:q['original']['metadata']['configs'][label] for label in LABELS}:
        raise ValueError('Configuration differs from qualified primary settings')
    records=audit['records'];expected={(label,c['id']) for label in LABELS for c in q['cases']}
    if len(records)!=40 or {(r['label'],r['case']) for r in records}!=expected:raise ValueError('Incomplete dev evidence')
    cases={c['id']:c for c in q['cases']};paths=[];verified_rows=[]
    ledger=root/'artifacts/round-2/cloud-budget.sqlite'
    with sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True) as db:
        paid={name:(identity,json.loads(result) if result else None) for name,identity,result in db.execute('SELECT id,identity,result FROM calls')}
    for row in records:
        path=folder/'slots'/f'{row["label"]}-{row["case"]}.json';state=read(path);response=state['result']
        if file_sha(path)!=row['checkpoint_sha256'] or digest(response)!=state['result_sha256'] or len(state['attempts'])!=1:
            raise ValueError('Dev checkpoint drift')
        checked=validate_response(response,ap_request(cases[row['case']],q['configs'][row['label']],q['prompt']))
        if checked['status']!=row['status'] or checked.get('rejection_codes',[])!=row['rejection_codes']:
            raise ValueError('Dev validator drift')
        identity=dict(iteration=q['sha256'],label=row['label'],case=row['case'],wire=q['contracts'][row['label']][row['case']])
        if state['identity']!=digest(identity):raise ValueError('Dev slot identity drift')
        if not row['label'].startswith('L'):
            entry=paid.get(f'round2b-qualification-v1-{row["label"]}-{row["case"]}')
            if entry!=(digest(identity),response):raise ValueError('Paid qualification evidence missing from ledger')
        if row['label'].startswith('L') and (response.get('reasoning_tokens')!=0 or response.get('reasoning_chars')!=0):
            raise ValueError('Dev reasoning not proven zero')
        verified_rows.append(dict(response,label=row['label'],case=row['case']))
        paths.append(path.relative_to(root).as_posix())
    verify_dev_summary(verified_rows,cases,audit['summary'])
    for label,model in q['models'].items():
        path=Path(model['path'])
        if path.stat().st_size!=model['bytes'] or file_sha(path)!=model['sha256']:raise ValueError('Weight drift: '+label)
        loads=list(folder.glob(f'load-{label}-session*.json'))
        if len(loads)!=1 or read(loads[0])['load_config']!=q['profiles'][label]:raise ValueError('Native load profile drift')
        paths.append(loads[0].relative_to(root).as_posix())
    verify_ledger_anchor(root/'artifacts/round-2/cloud-budget.sqlite',q['ledger_anchor'])
    paths+=sorted(q['files'])+['artifacts/round-2b/qualification/manifest.json',
        'artifacts/round-2b/qualification/audit.json','artifacts/round-2b/qualification/source-commit.txt']
    paths += [p.relative_to(root).as_posix() for p in sorted((folder/'requests').glob('*.json'))]
    return q,audit,paths


def verify_dev_summary(rows,cases,saved):
    actual=summarize(rows,cases)
    if actual!=saved:raise ValueError('Saved dev summary differs from verified responses')
    return actual


def verify(root,package):
    root=Path(root)
    verify_snapshot(root,package,list(package['files']))
    meta=package['metadata']
    if source_inventory(root)!=meta['source_inventory']:raise ValueError('Freeze source inventory drift')
    if meta['quality_authorized'] or meta['activated']:raise ValueError('Package is a STOP preflight, not activation')
    if meta['admission']['secondary']!=secondary_policy():raise ValueError('Secondary policy drift')
    if 'packages' in meta and meta['packages']!={name:importlib.metadata.version(name) for name in meta['packages']}:
        raise ValueError('Python dependency version drift')
    if 'python' in meta and meta['python']!=platform.python_version():raise ValueError('Python runtime drift')
    verify_external(meta['models'])
    verify_external(meta['environment'].get('installed_backend_binaries',{}))
    ledger=root/'artifacts/round-2/cloud-budget.sqlite'
    verify_ledger_anchor(ledger,meta['ledger'])
    if readonly_budget(ledger)<Decimal(meta['cloud_total_reserve']):raise ValueError('Remaining budget below frozen reserve')
    return True


def verify_external(records):
    for label,record in records.items():
        path=Path(record['path'])
        if not path.is_file() or path.stat().st_size!=record['bytes'] or file_sha(path)!=record['sha256']:
            raise ValueError('External file drift: '+label)


def prepare(root,folder,environment,*,l3_approved=False):
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root):raise ValueError('Freeze folder outside workspace')
    output=root/'docs/research/round2b/frozen-quality.json'
    if output.exists() or (folder/'private-seeds.json').exists():raise ValueError('Freeze outputs exist; never overwrite')
    q,audit,paths=qualification_evidence(root)
    policy=admission(audit['summary'],l3_approved)
    data=root/'docs/research/round2b/holdout-reviewed.json'
    completion=root/'docs/research/round2b/oracle-comparison-revision4.json'
    closed=json.loads(completion.read_text(encoding='utf-8'))
    if not closed['owner_oracle_complete'] or closed['open_disagreements'] or file_sha(data)!=closed['reviewed_holdout_sha256']:
        raise ValueError('Oracle not closed or reviewed corpus drift')
    cases=json.loads(data.read_text(encoding='utf-8'));validate_structure(cases)
    if file_sha(root/'docs/research/round2b/prompts/check-aprime-v1-uk.txt')!=PROMPT_SHA:
        raise ValueError('A-prime prompt drift')
    if hashlib.sha256(q['prompt'].encode()).hexdigest()!=PROMPT_SHA:raise ValueError('Qualified prompt differs')
    saved,wiremeta,reserves=contracts(cases,q['configs'],q['prompt'])
    ledger=root/'artifacts/round-2/cloud-budget.sqlite';available=readonly_budget(ledger)
    total=sum(map(Decimal,reserves.values()),Decimal(0))
    if total>available:raise ValueError('Full720-call quality reserve exceeds remaining budget')
    seed=secrets.randbits(128);review_seed=secrets.randbits(128);alias_seed=secrets.randbits(128)
    schedule=make_schedule([c['id'] for c in cases],list(q['configs']),seed,3)
    schedule=[dict({k:v for k,v in s.items() if k!='seed'},phase='quality') for s in schedule]
    if len(schedule)!=720 or Counter((s['config'],s['case']) for s in schedule)!=Counter({(l,c['id']):3 for l in LABELS for c in cases}):
        raise ValueError('Incomplete schedule coverage')
    folder.mkdir(parents=True,exist_ok=True)
    generated={'private-seeds.json':dict(execution_seed=seed,review_panel_seed=review_seed,model_alias_seed=alias_seed),
        'frozen-requests.json':saved,'schedule.json':schedule,'environment.json':environment}
    for name,value in generated.items():
        with (folder/name).open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
    paths+=source_inventory(root)+[p.relative_to(root).as_posix() for p in [data,completion]]
    paths += [(folder/name).relative_to(root).as_posix() for name in generated]
    paths+=['docs/research/2026-10-30-round2b-freeze-admission.md',
        'docs/research/2026-10-29-round-2-prompt-freeze-amendment.md',
        'docs/research/round2b/qualification-results.json','docs/research/round2b/qualification-content-review.json']
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    meta=dict(stage='round2b-quality-input-freeze',source_commit=commit,source_inventory=source_inventory(root),
        python=platform.python_version(),packages={name:importlib.metadata.version(name) for name in ['httpx','pydantic','python-dotenv']},
        inputs_frozen=True,activated=False,quality_authorized=False,execution_harness_complete=False,
        admission=policy,prompt_sha256=PROMPT_SHA,configs=q['configs'],models=q['models'],native_load_profiles=q['profiles'],
        contracts=wiremeta,slots=720,local_slots=432,cloud_slots=288,
        cloud_reserve_one_attempt=reserves,cloud_total_reserve=str(total),shared_available=str(available),ledger=ledger_anchor(ledger),
        metrics=dict(primary=dict(fp_max=7,fp_denominator=60,miss_max=10,miss_denominator=84,valid_min=137,valid_denominator=144),
            secondary=secondary_policy(),l6_invalid_report_separate=True,question_missed_split=['issue','empty','other/unreadable']),
        negative_control=dict(label='L5',comparator_pool=['L3'],dimensions=['false_positives','missed_facts','validity'],rule='Pareto dominance; conflicting metrics mean no unique conclusion'),
        constant_baselines=['always-issue','always-clean'],
        review_policy=dict(shared_panel=True,tp_minimum_per_model='0.20',selection_unit='case/draw/fact',
            algorithm='one fixed seeded order; expand shared panel until >=20%TP for each model',
            all_secondary_candidates_owner_review=True,blinded_model_aliases=True),
        seeds_private_file=(folder/'private-seeds.json').relative_to(root).as_posix(),
        environment=environment,limitations=[
            'Input/contract freeze only; existing legacy frozen_send uses A and round2 output paths. A guarded A-prime/round2b execution adapter is not activated or claimed complete.',
            'Any new execution adapter requires review and an updated execution freeze before the first holdout call; this package alone never authorizes dispatch.',
            'Post-repair owner oracle reused known examples; not a fresh independent blinded sample.',
            'Current environment is a point observation, not continuous power/temperature/VRAM measurement.',
            'Dirty owner plan is identified by byte hash and private source archive; source commit alone is insufficient.',
            'Cloud aliases may change underlying weights; record response model IDs and stop on unreviewed drift.'])
    package=snapshot(root,paths,meta);verify(root,package)
    with output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(package,stream,ensure_ascii=False,indent=2)
    return package
