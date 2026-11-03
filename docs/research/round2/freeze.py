"""Offline freeze primitives: immutable identity, native wire hashes and budget.

No model/API calls, dotenv, authentication or paid dispatch. Activation waits for
the complete runner/review implementation and final review, not just this module.
"""
from copy import deepcopy
from contextlib import closing
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3

from .cloud import usage_cost
from .requests import build_request
from .runner import digest,make_schedule
from .transports import envelope
from .weights import file_hash,safe_name


CONFIG_KEYS=(
    'experiment','holdout_approved','holdout_sha256','author','seed','schedule','result_cap_characters',
    'max_concerns','local_temperature','local_reasoning_effort','max_output_tokens','transport_attempts_limit',
    'cloud_models','cloud_budget_approved','cloud_budget_usd','weights_prepared','dev_qualified','dev_admission',
    'primary_prompt','secondary_policy','review_policy','bonus_order','B7','holdout_lifecycle','paired_12b_load',
    'l5_comparison',
)


def active_configs(manifest):
    approved={'C1':dict(provider='google',model='gemini-3.5-flash-lite'),
              'C2':dict(provider='anthropic',model='claude-haiku-5-5')}
    if manifest.get('cloud_models')!=approved:raise ValueError('Unapproved cloud participants')
    configs={label:dict(provider='local',model=key,
                       context_tokens=32768 if label in {'L3','L4'} else 131072,timeout=300)
             for label,key in [('L1','l1'),('L2','l2'),('L3','l3'),('L4','l4'),
                               ('L5','huihui-qwen3.5-4b-abliterated'),('L6','l6')]}
    configs.update({label:dict(**config,schema_relaxation_approved=label=='C2',timeout=300)
                    for label,config in approved.items()})
    return configs


def source_inventory(root):
    root=Path(root)
    paths=list((root/'src/storygen').rglob('*.py'))+list((root/'docs/research').rglob('*.py'))
    resources=root/'src/storygen/generation/resources'
    paths.extend(p for p in resources.rglob('*') if p.is_file())
    paths.extend(root/name for name in ['pyproject.toml','requirements-lock.txt'] if (root/name).is_file())
    return sorted({p.relative_to(root).as_posix() for p in paths if '__pycache__' not in p.parts})


def sent_text_hash(path):
    return hashlib.sha256(Path(path).read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def primary_config(manifest):
    return deepcopy({key:manifest[key] for key in CONFIG_KEYS if key in manifest})


def blinding_seed(root,policy):
    if 'blind_labels_seed' in policy:raise ValueError('Public blinding seed discloses model aliases')
    seed=json.loads(_path(root,policy['blinding_seed_file']).read_text(encoding='utf-8'))['seed']
    if type(seed) is not int or digest(seed)!=policy.get('blind_labels_seed_sha256'):
        raise ValueError('Private blinding seed commitment mismatch')
    return seed


def _path(root,name):
    safe_name(name)
    if any(part=='.env' or part.startswith('.env.') or part in {'.git','.aws'} for part in [p.lower() for p in Path(name).parts]):
        raise ValueError('Secret path is not a freeze input')
    path=Path(root).resolve()/name
    if not path.resolve().is_relative_to(Path(root).resolve()):raise ValueError('Freeze path escapes root')
    return path


def snapshot(root,paths,metadata):
    names=sorted(set(paths))
    hashes={name:file_hash(_path(root,name)) for name in names}
    result=dict(version=1,files=hashes,metadata=deepcopy(metadata))
    return dict(result,snapshot_sha256=digest(result))


def verify_snapshot(root,data,current_paths):
    value={k:v for k,v in data.items() if k!='snapshot_sha256'}
    if digest(value)!=data.get('snapshot_sha256'):raise ValueError('Frozen snapshot checksum mismatch')
    if sorted(set(current_paths))!=sorted(data['files']):raise ValueError('Frozen source inventory changed')
    for name,expected in data['files'].items():
        path=_path(root,name)
        if not path.is_file() or file_hash(path)!=expected:raise ValueError('Frozen file drift: '+name)


def check_gates(manifest,dev):
    if not all(manifest.get(k) is True for k in ['holdout_approved','weights_prepared','dev_qualified']):
        raise ValueError('Holdout/weights/dev gates not met')
    prompt=manifest.get('primary_prompt',{})
    if prompt.get('condition')!='A' or prompt.get('tuning_stopped') is not True:raise ValueError('Primary prompt must be frozen A')
    policy=manifest.get('secondary_policy',{})
    if (policy.get('scope_approved_in_chat') is not True or
            set(policy.get('closed_defects',[]))!={'incomplete_processing','duplicate_source_reference'}):
        raise ValueError('Secondary policy is not approved')
    if manifest.get('review_policy',{}).get('approved') is not True:raise ValueError('Shared review policy not approved')
    if manifest.get('cloud_budget_approved') is not True or manifest.get('cloud_budget_usd')!='10.00':
        raise ValueError('Shared cloud budget gate not met')
    for label in ['L1','L2','L3','L4','L5','L6','C1','C2']:
        evidence=dev.get(label,{})
        if evidence.get('calls')!=8:raise ValueError('Missing original eight-case dev evidence: '+label)
        if label.startswith('L'):
            values=evidence.get('reasoning_tokens_observed',[])
            if len(values)!=8 or any(type(v) is not int or v!=0 for v in values):
                raise ValueError('Local dev reasoning not proven off: '+label)


def native_parts(wire,provider):
    body=wire['body']
    if provider=='anthropic':return body['system'],body['output_config']['format']['schema']
    if provider=='google':return body['systemInstruction']['parts'][0]['text'],body['generationConfig']['responseJsonSchema']
    return body['messages'][0]['content'],body['response_format']['json_schema']['schema']


def wire_contracts(cases,configs):
    contracts={}
    for label,config in configs.items():
        entries={}
        for case in cases:
            request=build_request(case,config);wire=envelope(request['body'],config['provider'],config)
            system,schema=native_parts(wire,config['provider'])
            entries[case['id']]=dict(wire_sha256=digest(wire),schema_sha256=digest(schema),
                system_sha256=hashlib.sha256(system.encode('utf-8')).hexdigest(),
                schema_deviations=wire['schema_deviations'],
                input_wire_bytes=len(json.dumps(wire['body'],ensure_ascii=False,separators=(',',':')).encode('utf-8')))
        contracts[label]=entries
    return contracts


def reserve_for_wire(model,wire,*,day=None):
    """Conservative Standard tariff reserve, not an assertion of billed tokens.

    Entire UTF8 wire bytes count as input tokens plus8192 wrapper/schema margin.
    Output cap includes thinking. No tools/cache writes/batch/priority surcharges.
    Full output-cap reserve is used even when earlier replies were much shorter.
    """
    body=wire['body']
    if any(key in body for key in ['tools','cachedContent','cache_control','service_tier']):
        raise ValueError('Unsupported billable request feature')
    maximum=body['generationConfig']['maxOutputTokens'] if model.startswith('gemini-') else body['max_tokens']
    if type(maximum) is not int or maximum!=4096:raise ValueError('Frozen output reserve must be4096')
    upper=len(json.dumps(body,ensure_ascii=False,separators=(',',':')).encode('utf-8'))+8192
    usage=(dict(promptTokenCount=upper,candidatesTokenCount=maximum,thoughtsTokenCount=0,totalTokenCount=upper+maximum)
           if model.startswith('gemini-') else dict(input_tokens=upper,output_tokens=maximum))
    return usage_cost(model,usage,day=day)


def _ledger_rows(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Research ledger is missing; do not reset budget')
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            if db.execute('SELECT value FROM metadata WHERE key=?',('limit_usd',)).fetchone()!=('10.00',):
                raise ValueError('Research ledger limit mismatch')
            rows=list(db.execute('SELECT id,identity,reserve,charged,result FROM calls ORDER BY id'))
            charges=[]
            for _,_,reserve,charged,_ in rows:
                if charged is not None and Decimal(charged)>Decimal(reserve):
                    raise ValueError('Provider exceeded reserve; review ledger')
                value=Decimal(charged if charged is not None else reserve)
                if not value.is_finite() or value<0:raise ValueError('Invalid ledger amount')
                charges.append(value)
        return rows,Decimal('10.00')-sum(charges,Decimal(0))
    except sqlite3.Error:
        raise ValueError('Research ledger cannot be read') from None


def readonly_budget(path):
    return _ledger_rows(path)[1]


def verify_model_files(models):
    for label,model in models.items():
        path=Path(model['path'])
        if not path.is_file() or path.stat().st_size!=model['bytes'] or file_hash(path)!=model['sha256']:
            raise ValueError('Research weight identity changed: '+label)


def audit_dev(root,configs):
    from .dev import old_cases
    from .scoring import validate_response
    root=Path(root);summary={};paths=[]
    for label,cfg in configs.items():
        folder=root/'artifacts/round-2/dev'/label;statuses=[];reasoning=[]
        for case in old_cases():
            request=build_request(case,cfg)
            req_path=folder/(case['id']+'-request.json')
            saved=json.loads(req_path.read_text(encoding='utf-8'))
            local=cfg['provider']=='local'
            expected=request['body'] if local else envelope(request['body'],cfg['provider'],cfg)
            if saved!=expected:raise ValueError('Original dev request drift: '+label)
            path=folder/'slots'/(case['id']+'.json') if local else folder/(case['id']+'-response.json')
            data=json.loads(path.read_text(encoding='utf-8'))
            result=data['result'] if local else data
            if local and data.get('result_sha256')!=digest(result):raise ValueError('Dev reply checksum mismatch')
            checked=validate_response(result,request)
            if result['status']!=checked['status']:raise ValueError('Dev strict status changed')
            statuses.append(result['status']);reasoning.append(result.get('reasoning_tokens'))
            if local and (result.get('reasoning_tokens')!=0 or result.get('reasoning_chars')!=0):
                raise ValueError('Original local dev reasoning not proven zero')
            paths.extend([req_path.relative_to(root).as_posix(),path.relative_to(root).as_posix()])
        summary[label]=dict(calls=len(statuses),valid=statuses.count('valid'),
                            invalid=statuses.count('invalid'),refusals=statuses.count('refusal'),
                            reasoning_tokens_observed=reasoning)
    return dict(summary=summary,files=paths)


def ledger_anchor(path):
    rows,available=_ledger_rows(path)
    return dict(entries={r[0]:digest(list(r[1:])) for r in rows},available_when_frozen=str(available))


def verify_ledger_anchor(path,anchor):
    current=ledger_anchor(path)
    if not all(current['entries'].get(key)==value for key,value in anchor['entries'].items()):
        raise ValueError('Research ledger reset or baseline entries changed')


def freeze_candidate(root,paths,manifest,cases,configs,ledger,*,code_commit,day=None):
    """Build a non-dispatchable candidate; activation is a separate reviewed step."""
    if len(code_commit)!=40 or any(c not in '0123456789abcdef' for c in code_commit):
        raise ValueError('Full code commit required')
    schedule=make_schedule([c['id'] for c in cases],list(configs),manifest['seed'],3)
    metadata=dict(activated=False,code_commit=code_commit,
        configuration_sha256=digest(primary_config(manifest)),configs=deepcopy(configs),
        cases_sha256=digest(cases),contracts=wire_contracts(cases,configs),schedule=schedule,
        ledger=ledger_anchor(ledger))
    result=snapshot(root,paths,metadata)
    prepare_candidate(root,paths,result,manifest,cases,configs,ledger,day=day)
    return result


def prepare_candidate(root,paths,frozen,manifest,cases,configs,ledger,*,day=None):
    """Pure read-only verification. No key reads, model loads or network access."""
    verify_snapshot(root,frozen,paths);meta=frozen['metadata']
    if meta['configuration_sha256']!=digest(primary_config(manifest)) or meta['configs']!=configs:
        raise ValueError('Frozen configuration changed')
    if meta['cases_sha256']!=digest(cases) or meta['contracts']!=wire_contracts(cases,configs):
        raise ValueError('Frozen case/native contract changed')
    schedule=make_schedule([c['id'] for c in cases],list(configs),manifest['seed'],3)
    if meta['schedule']!=schedule:raise ValueError('Frozen schedule changed')
    verify_ledger_anchor(ledger,meta['ledger'])
    reserves={label:Decimal(0) for label,cfg in configs.items() if cfg['provider']!='local'}
    for case in cases:
        for label,cfg in configs.items():
            wire=envelope(build_request(case,cfg)['body'],cfg['provider'],cfg)
            if cfg['provider']=='local':
                # Conservative whole-wire byte bound; no truncation/chunking of research cases.
                size=len(json.dumps(wire['body'],ensure_ascii=False).encode('utf-8'))
                if size+8192+4096>cfg['context_tokens']:raise ValueError('Local context bound exceeded')
            else:reserves[label]+=3*reserve_for_wire(cfg['model'],wire,day=day)
    one=sum(reserves.values(),Decimal(0));available=readonly_budget(ledger)
    if one>available:raise ValueError('Insufficient shared research budget for primary series')
    return dict(status='prepared-candidate' if not meta['activated'] else 'prepared-frozen',
        inference_performed=False,primary_slots=len(schedule),
        local_slots=sum(configs[s['config']]['provider']=='local' for s in schedule),
        cloud_slots=sum(configs[s['config']]['provider']!='local' for s in schedule),
        timing_slots=48,warmup_slots=6,
        cloud_reserve_one_attempt={k:str(v) for k,v in reserves.items()},
        cloud_total_one_attempt=str(one),cloud_total_three_attempts=str(3*one),
        shared_available=str(available),
        three_attempts_fit=3*one<=available,
        senior_reserve_included=False,
        reserve_note='UTF8 wire bytes +8192 input margin and4096 output; reserve, not billed-token estimate')


def activate_candidate(candidate,review):
    body={k:v for k,v in candidate.items() if k!='snapshot_sha256'}
    if (digest(body)!=candidate.get('snapshot_sha256') or
        review.get('candidate_sha256')!=candidate['snapshot_sha256'] or
        review.get('critical')!=0 or review.get('important')!=0 or review.get('tests_passed') is not True):
        raise ValueError('Exact candidate review and successful tests required before activation')
    value=deepcopy(body);value['metadata'].update(activated=True,final_review=deepcopy(review))
    return dict(value,snapshot_sha256=digest(value))


def workspace_inputs(root):
    """Resolve existing approved assets; never creates missing dev or budget data."""
    root=Path(root)
    def read(name):return json.loads(_path(root,name).read_text(encoding='utf-8'))
    manifest=read('docs/research/round2/manifest.json');configs=active_configs(manifest)
    cases=read('docs/research/round2/holdout.json')
    from .dataset import validate_dataset
    validate_dataset(cases)
    if file_hash(root/'docs/research/round2/holdout.json')!=manifest['holdout_sha256']:
        raise ValueError('Approved holdout hash changed')
    for data in [manifest['primary_prompt'],manifest['B7']]:
        if sent_text_hash(root/data.get('source',data.get('path')))!=data['sha256_sent_utf8']:
            raise ValueError('Approved prompt hash changed')
    audit=audit_dev(root,configs);check_gates(manifest,audit['summary'])
    blinding_seed(root,manifest['review_policy'])
    summary=read('docs/research/round2/dev-summary.json')
    for label,evidence in audit['summary'].items():
        if any(summary[label][k]!=evidence[k] for k in ['calls','valid','invalid','refusals','reasoning_tokens_observed']):
            raise ValueError('Dev summary differs from original replies: '+label)
    provenance=read('docs/research/round2/weights-provenance.json');models={}
    for row in provenance['conversions']:
        models[row['configuration']]=dict(path=str(root/row['quantized_file']),
            bytes=row['quantized_bytes'],sha256=row['quantized_sha256'])
    l5=provenance['existing_L5'];l6=provenance['L6']
    models['L5']=dict(path=str(Path.home()/'.lmstudio/models'/l5['repo']/l5['filename']),bytes=l5['bytes'],sha256=l5['sha256'])
    models['L6']=dict(path=str(root/'artifacts/round-2/weights/L6'/l6['filename']),bytes=l6['bytes'],sha256=l6['sha256'])
    paths=source_inventory(root)+audit['files']+[manifest['review_policy']['blinding_seed_file'],
        'docs/research/round2/holdout.json','docs/research/round2/weights-provenance.json',
        'docs/research/round2/dev-summary.json','docs/research/round2/prompts/check-focused-uk.txt',
        'docs/research/2026-10-28-round-2-codex-brief.md',
        'docs/research/2026-10-29-round-2-cloud-amendment.md',
        'docs/research/2026-10-29-round-2-prompt-freeze-amendment.md',
        'artifacts/round-2/preflight/paired-load-checks.json',
        'artifacts/round-2/preflight/model-links.json']
    for label in ['L1','L2','L3','L4','L5','L6']:
        paths.extend(f'artifacts/round-2/dev/{label}/{name}' for name in ['load.json','gpu-loaded.json','inventory-after.json'])
    return manifest,cases,configs,models,sorted(set(paths))


def workspace_candidate(root,*,day=None):
    import importlib.metadata
    import platform
    import subprocess
    root=Path(root);manifest,cases,configs,models,paths=workspace_inputs(root)
    verify_model_files(models)
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
    candidate=freeze_candidate(root,paths,manifest,cases,configs,root/'artifacts/round-2/cloud-budget.sqlite',
                               code_commit=commit,day=day)
    meta=candidate['metadata']
    from .dev import old_cases
    meta['timing_contracts']=wire_contracts(old_cases(),{k:v for k,v in configs.items() if v['provider']=='local'})
    meta['models']=models
    def read(name):return json.loads((root/name).read_text(encoding='utf-8'))
    profiles={label:read(f'artifacts/round-2/dev/{label}/load.json')['load_config'] for label in models}
    for row in read('artifacts/round-2/preflight/paired-load-checks.json'):
        profiles[row['model'].upper()]=row['load']['load_config']
    meta['native_load_profiles']=profiles
    meta['packages']={name:importlib.metadata.version(name) for name in ['httpx','pydantic','python-dotenv']}
    meta['python']=platform.python_version()
    meta['runtime']=json.loads((root/'docs/research/round2/dev-summary.json').read_text(encoding='utf-8'))['runtime']
    meta['runtime_limitations']=[
        'Native REST does not expose GPU-layer count; paired load evidence records UI38/engine39.',
        'Runtime source commit unknown; binary hashes identify observed installation, not future GUI selection.',
        'Power state observed after dev, not continuously logged.',
        'Cloud aliases may change underlying backend weights; retain actual response model version.']
    return snapshot(root,paths,meta)


def workspace_prepare(root,frozen,*,verify_weights=True,day=None):
    import importlib.metadata
    import platform
    root=Path(root);manifest,cases,configs,models,paths=workspace_inputs(root)
    meta=frozen['metadata']
    if models!=meta['models']:raise ValueError('Research weight configuration drift')
    if verify_weights:verify_model_files(models)
    from .local_models import verify_imports
    registry=json.loads((root/'artifacts/round-2/preflight/model-links.json').read_text(encoding='utf-8'))
    verify_imports(models,registry)
    if platform.python_version()!=meta['python'] or any(importlib.metadata.version(k)!=v for k,v in meta['packages'].items()):
        raise ValueError('Research dependency versions changed')
    return prepare_candidate(root,paths,frozen,manifest,cases,configs,root/'artifacts/round-2/cloud-budget.sqlite',day=day)
