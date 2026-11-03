"""Round2b gate one: paired weights x concerns.maxItems, local-only and opt-in."""
from copy import deepcopy
from collections import Counter
from itertools import groupby
import hashlib
import json
import os
from pathlib import Path
import random

from round2.requests import build_request
from round2.runner import digest, atomic_json, run_slot
from round2.transports import dispatch, envelope
from round2.freeze import verify_snapshot, source_inventory
from round2.local_models import loaded_model, inventory

CELLS=('own3','own1','unsloth3','unsloth1')
SEED=2026102904
UNSLOTH_SHA='03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8'

class ProfileClient:
    """Add approved per-load overrides; retain frozen owned-load lifecycle."""
    def __init__(self,client,profile):self.client=client;self.profile=profile
    def get(self,*args,**kwargs):return self.client.get(*args,**kwargs)
    def post(self,url,*,json,**kwargs):
        if url.endswith('/api/v1/models/load'):
            json=dict(json,speculative_draft_mtp=self.profile['speculative_draft_mtp'],
                      prompt_template=self.profile['prompt_template'])
        return self.client.post(url,json=json,**kwargs)

def schema_diff(a,b,path=''):
    if type(a) is not type(b):return [path]
    if isinstance(a,dict):
        return [p for k in sorted(set(a)|set(b)) for p in
                ([path+'/'+k] if k not in a or k not in b else schema_diff(a[k],b[k],path+'/'+k))]
    if isinstance(a,list):
        if len(a)!=len(b):return [path]
        return [p for i,(x,y) in enumerate(zip(a,b)) for p in schema_diff(x,y,path+'/'+str(i))]
    return [] if a==b else [path]

def clean_cases(cases):
    selected=[c for c in cases if c['family']!='D' and c['gold']['verdict']=='clean']
    if len(selected)!=16 or len({c['id'] for c in selected})!=16:raise ValueError('Expected16 clean cases without D')
    return selected

def build_pair(case,model):
    three=build_request(case,dict(model=model,context_tokens=131072))
    one=deepcopy(three)
    schema=lambda r:r['body']['response_format']['json_schema']['schema']
    if schema(three)['properties']['concerns']['maxItems']!=3:raise ValueError('Original schema changed')
    schema(one)['properties']['concerns']['maxItems']=1
    if schema_diff(schema(one),schema(three))!=['/properties/concerns/maxItems']:
        raise ValueError('Schema diff exceeds concerns.maxItems')
    return one,three

def schedule(ids):
    ids=list(ids);random.Random(SEED).shuffle(ids)
    if len(ids)!=16 or len(set(ids))!=16:raise ValueError('Expected16 case IDs')
    out=[]
    for block in range(2):
        cells=CELLS[block:]+CELLS[:block]
        for cell in cells:
            for case in ids[block*8:(block+1)*8]:out.append(dict(block=block,cell=cell,case=case))
    return out

def check_request_hash(request,expected):
    if digest(request['body'])!=expected:raise ValueError('Canonical wire drift')

def file_sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def verify_model_binding(model,catalogue):
    source=Path(model['path']);registered=Path(model['registered_path'])
    if (not registered.is_file() or registered.is_symlink() or not source.is_file()
            or not os.path.samefile(source,registered) or file_sha(source)!=model['sha256']):
        raise ValueError('Registered model file binding changed')
    rows=[r for r in catalogue if r.get('key')==model['key']]
    if len(rows)!=1 or rows[0].get('publisher')!=model['publisher'] or rows[0].get('size_bytes')!=model['bytes']:
        raise ValueError('Native catalogue binding changed')

def verify_guard(root,manifest,*,inventory=source_inventory):
    root=Path(root)
    verify_snapshot(root,manifest['original'],list(manifest['original']['files']))
    if inventory(root)!=manifest['source_inventory']:raise ValueError('Diagnostic source inventory changed')
    for name,sha in manifest['extra_files'].items():
        if file_sha(root/name)!=sha:raise ValueError('Diagnostic file drift: '+name)

def prepare(root,folder):
    root=Path(root);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'manifest.json').exists():raise ValueError('Manifest exists; never overwrite frozen diagnostic evidence')
    read=lambda p:json.loads((root/p).read_text(encoding='utf-8'))
    original=read('docs/research/round2/frozen-primary.json')
    verify_snapshot(root,original,list(original['files']))
    cases=clean_cases(read('docs/research/round2/holdout.json'))
    own=deepcopy(original['metadata']['models']['L1'])
    other=dict(path=str(Path.home()/'.lmstudio/models/unsloth/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf'),
               bytes=5680522464,sha256=UNSLOTH_SHA)
    for m in [own,other]:
        path=Path(m['path'])
        if not path.is_file() or path.stat().st_size!=m['bytes'] or file_sha(path)!=m['sha256']:
            raise ValueError('Weight missing or SHA mismatch')
    registry=read('artifacts/round-2/preflight/model-links.json')
    models=dict(own=dict(own,key='l1',registered_path=registry['links']['L1'],publisher='round2-r28l'),
                unsloth=dict(other,key='qwen3.5-9b',registered_path=other['path'],publisher='unsloth'))
    contracts={};diffs={}
    for cell in CELLS:
        model=models['own' if cell.startswith('own') else 'unsloth']['key'];contracts[cell]={}
        for case in cases:
            one,three=build_pair(case,model);req=one if cell.endswith('1') else three
            schema=lambda r:r['body']['response_format']['json_schema']['schema']
            contracts[cell][case['id']]=dict(wire_sha256=digest(req['body']),schema_sha256=digest(schema(req)))
            diffs[case['id']]=schema_diff(schema(one),schema(three))
    current=source_inventory(root)
    allowed={'docs/research/round2b/spike.py','docs/research/round2b/test_spike.py','docs/research/r28m-spike.py'}
    added=set(current)-set(original['files'])
    if added!=allowed:raise ValueError('Unexpected new source inventory: '+str(sorted(added)))
    extra=allowed|{'docs/research/2026-10-29-round-2b-codex-brief.md',
                   'docs/research/2026-10-29-round-2b-holdout-rebuild-plan.md',
                   'docs/research/2026-10-29-round-2-holdout-audit.md',
                   'docs/research/2026-10-29-round-2-diagnostics-amendment.md',
                   'docs/research/2026-10-29-round-2b-spike-mtp-amendment.md',
                   'artifacts/round-2/preflight/model-links.json'}
    profile=deepcopy(original['metadata']['native_load_profiles']['L1'])
    profile['speculative_draft_mtp']=False
    l2_profile=original['metadata']['native_load_profiles']['L2']
    l2_counts={}
    for phase,paths in [('dev',sorted((root/'artifacts/round-2/dev/L2/slots').glob('*.json'))),
                        ('quality',sorted((root/'artifacts/round-2/quality/slots').glob('quality-L2-*.json')))]:
        positive=0;present=0;total=0;accepted=0
        for path in paths:
            saved=json.loads(path.read_text(encoding='utf-8'))
            if digest(saved['result'])!=saved['result_sha256']:raise ValueError('L2 checkpoint SHA drift')
            stats=saved['result'].get('raw_response',{}).get('stats',{})
            present+='total_draft_tokens_count' in stats
            positive+=stats.get('total_draft_tokens_count',0)>0
            total+=stats.get('total_draft_tokens_count',0);accepted+=stats.get('accepted_draft_tokens_count',0)
        if len(paths)!=(8 if phase=='dev' else 144) or positive!=len(paths):raise ValueError('L2 MTP provenance differs')
        l2_counts[phase]=dict(calls=len(paths),draft_counter_present=present,positive_draft_calls=positive,draft_tokens=total,accepted_draft_tokens=accepted)
    value=dict(stage='round2b-fp-spike',seed=SEED,original=original,source_inventory=current,
               extra_files={p:file_sha(root/p) for p in sorted(extra)},models=models,cases=cases,
               schedule=schedule([c['id'] for c in cases]),contracts=contracts,schema_diffs=diffs,
               profile=profile,response_character_limit=4096,
               max_output_tokens=4096,temperature=0.1,reasoning='none',threshold=7,denominator=16,
               anchor=dict(cell='own3',metric='strict_fp',minimum=14,denominator=16,
                           failure_action='descriptive_only; no causal/participant ruling'),
               mtp_deviation='Owner approved MTPoff all four cells; own3 is not an exact reproduction of primary MTPon.',
               l2_provenance=dict(speculative_draft_mtp=l2_profile['speculative_draft_mtp'],
                                  external_draft_model=l2_profile['speculative_draft_model'],counts=l2_counts),
               purpose='diagnostic; former holdout is dev; no D; no primary result changes')
    value['sha256']=digest(value)
    atomic_json(folder/'manifest.json',value)
    return value

def summarize(rows):
    cells={}
    for cell in CELLS:
        selected=[r for r in rows if r['cell']==cell];counts=Counter(r['status'] for r in selected)
        nonempty=0;fp=0;tn=0
        for r in selected:
            try:concerns=json.loads(r.get('text') or 'null')['concerns']
            except (ValueError,TypeError,KeyError):concerns=None
            if concerns:nonempty+=1
            if r['status']=='valid':
                fp+=bool(concerns);tn+=not concerns
        cells[cell]=dict(calls=len(selected),fp=fp,tn=tn,invalid=counts['invalid'],refusal=counts['refusal'],
                         nonempty_including_invalid=nonempty)
    complete=all(v['calls']==16 for v in cells.values())
    differences=dict(schema_own=cells['own3']['fp']-cells['own1']['fp'],
                     schema_unsloth=cells['unsloth3']['fp']-cells['unsloth1']['fp'],
                     weights_max3=cells['own3']['fp']-cells['unsloth3']['fp'],
                     weights_max1=cells['own1']['fp']-cells['unsloth1']['fp'])
    effect=lambda a,b:complete and abs(a)>=7 and abs(b)>=7 and a*b>0
    schema_observed=effect(differences['schema_own'],differences['schema_unsloth'])
    weight_observed=effect(differences['weights_max3'],differences['weights_max1'])
    anchor=cells['own3']['fp']>=14 if complete else None
    return dict(cells=cells,complete=complete,differences=differences,anchor_minimum=14,anchor_passed=anchor,
                schema_difference_meets_threshold=schema_observed,weight_difference_meets_threshold=weight_observed,
                schema_effect=bool(anchor and schema_observed),weight_effect=bool(anchor and weight_observed),
                participant_ruling_allowed=bool(complete and anchor))

def execute(root,folder,client,*,authorized=False,max_groups=None):
    if not authorized:raise ValueError('Local spike not authorized')
    root=Path(root);folder=Path(folder);manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if digest({k:v for k,v in manifest.items() if k!='sha256'})!=manifest['sha256']:raise ValueError('Manifest checksum changed')
    verify_guard(root,manifest)
    (folder/'requests').mkdir(parents=True,exist_ok=True)
    before=inventory(client)
    if not (folder/'inventory-before.json').exists():atomic_json(folder/'inventory-before.json',before)
    if any(r.get('loaded_instances') for r in before):raise ValueError('Owner model loaded; coordinate first')
    cases={c['id']:c for c in manifest['cases']};groups=0;rows=[]
    for (block,cell),items in groupby(manifest['schedule'],key=lambda s:(s['block'],s['cell'])):
        slots=list(items);model=manifest['models']['own' if cell.startswith('own') else 'unsloth']
        def slot_path(s):return folder/'slots'/f"{s['cell']}-{s['case']}.json"
        needed=any(not slot_path(s).exists() or 'result' not in json.loads(slot_path(s).read_text(encoding='utf-8')) for s in slots)
        if needed and max_groups is not None and groups>=max_groups:break
        # Replay completed slots without loading a model.
        from contextlib import nullcontext
        context=loaded_model(ProfileClient(client,manifest['profile']),model['key'],131072,expected_profile=manifest['profile'],expected_size=model['bytes']) if needed else nullcontext({})
        if needed:
            verify_guard(root,manifest)
            verify_model_binding(model,inventory(client))
        with context as loaded:
            if needed:
                groups+=1;epoch=1
                while (folder/f'load-b{block}-{cell}-session{epoch}.json').exists():epoch+=1
                load_path=folder/f'load-b{block}-{cell}-session{epoch}.json'
                atomic_json(load_path,loaded)
            for slot in slots:
                req=build_pair(cases[slot['case']],model['key'])[0 if cell.endswith('1') else 1]
                check_request_hash(req,manifest['contracts'][cell][slot['case']]['wire_sha256'])
                identity=dict(diagnostic=manifest['sha256'],slot=slot)
                def send():
                    verify_guard(root,manifest)
                    instance=loaded.get('instance_id') or loaded.get('model_instance_id')
                    cfg=dict(model=instance,timeout=300)
                    actual=envelope(req['body'],'local',cfg)
                    atomic_json(folder/'requests'/f"{cell}-{slot['case']}.json",dict(actual,canonical_wire_sha256=digest(req['body']),load_session=load_path.name))
                    return dispatch(client,req,'local',cfg,authorized=True)
                result=run_slot(folder/'slots',f"{cell}-{slot['case']}",identity,send,authorized=True)
                rows.append(dict(result,cell=cell,case=slot['case']))
                atomic_json(folder/'progress.json',dict(completed=len(rows),total=64,last=slot,summary=summarize(rows)))
                print(json.dumps(dict(completed=len(rows),total=64,cell=cell,case=slot['case'],status=result['status'],seconds=result.get('seconds')),ensure_ascii=False),flush=True)
                if result.get('reasoning_tokens')!=0 or result.get('reasoning_chars')!=0:
                    raise ValueError('Reasoning not proven off; saved response retained')
    atomic_json(folder/'summary.json',summarize(rows))
    return summarize(rows)
