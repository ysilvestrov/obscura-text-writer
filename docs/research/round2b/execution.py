"""A-prime execution boundary. Dry-run never creates an HTTP client."""
from copy import deepcopy
from contextlib import contextmanager
from decimal import Decimal
import base64
import hashlib
import json
import os
import platform
import importlib.metadata
from pathlib import Path
import time

import httpx
from round2.runner import digest,atomic_json
from round2.transports import envelope,normalize,ProviderHTTPError
from round2.scoring import validate_response
from round2.experiment import slot_id,execute_schedule
from round2.local_models import loaded_model,inventory
from round2.cloud import paid_call,usage_cost
from round2.freeze import verify_snapshot,source_inventory,verify_ledger_anchor,readonly_budget,reserve_for_wire
from round2b.freeze import verify_external
from round2b.dev import ap_request
from round2b.spike import verify_model_binding

INPUT_SHA='ce1b4068175e470d3671c93bf1c23c7d568643992638306b0ec6cbe8734f291d'
ADDED_SOURCES={'docs/research/round2b/execution.py','docs/research/round2b/test_execution.py','docs/research/r28q-round2b-execution.py'}


def sha(data):return hashlib.sha256(data).hexdigest()


def body_bytes(body):
    # Match the pinned HTTPX json= encoder, preserving the frozen schema/key order.
    return json.dumps(body,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


def runtime_guard(meta):
    if meta['python']!=platform.python_version() or any(importlib.metadata.version(k)!=v for k,v in meta['packages'].items()):
        raise ValueError('Frozen Python runtime or dependency version drift')


class Adapter:
    def __init__(self,root,cases,configs,prompt,saved,contracts,schedule,profiles,input_id,models=None):
        self.root=Path(root).resolve();self.cases={c['id']:deepcopy(c) for c in cases}
        self.configs=deepcopy(configs);self.prompt=prompt;self.saved=deepcopy(saved)
        self.contracts=deepcopy(contracts);self.schedule=deepcopy(schedule);self.profiles=deepcopy(profiles)
        self.input_id=input_id;self.models=deepcopy(models or {});self.execution_id=None;self.execution_package=None
        self.active_backend={};self.client=None
        self.allowed_slots={digest(s) for s in schedule};self.byte_contracts={}
        for label,items in self.saved.items():
            self.byte_contracts[label]={}
            for case,item in items.items():
                if digest(item['wire'])!=self.contracts[label][case]['wire_sha256']:raise ValueError('Frozen wire identity mismatch')
                self.byte_contracts[label][case]=sha(body_bytes(item['wire']['body']))

    def check_slot(self,slot):
        if digest(slot) not in self.allowed_slots:raise ValueError('Unknown frozen execution slot')

    def namespace_root(self):
        base=self.root/'artifacts/round-2b'
        if base.resolve()!=base:raise ValueError('Output namespace redirected outside round2b')
        return base

    def paths(self,slot):
        self.check_slot(slot);name=slot_id(slot)
        if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in name):raise ValueError('Unsafe slot path')
        base=self.namespace_root()/'quality'
        paths=dict(request=base/'requests'/f'{name}.bin',request_meta=base/'requests'/f'{name}.json',result=base/'slots'/f'{name}.json')
        if any(path.resolve()!=path for path in paths.values()):raise ValueError('Output namespace redirected outside round2b')
        return paths

    def check_backend(self,label,echo):
        if not isinstance(echo,dict):raise ValueError('Missing fresh backend echo')
        if echo.get('load_config')!=self.profiles[label]:raise ValueError('Backend echo profile differs from qualification')
        if (echo.get('instance_id') or echo.get('model_instance_id'))!=self.configs[label]['model']:
            raise ValueError('Backend model ID cannot preserve frozen model bytes')
        return True

    def prepare(self,slot,*,echo=None,wire=None):
        self.check_slot(slot);label=slot['config'];case=slot['case'];cfg=self.configs[label]
        if cfg['provider']=='local':self.check_backend(label,echo)
        request=ap_request(self.cases[case],cfg,self.prompt)
        if digest(request)!=digest(self.saved[label][case]['request']):raise ValueError('Frozen validation request drift')
        wire=envelope(request['body'],cfg['provider'],cfg) if wire is None else deepcopy(wire)
        if digest(wire)!=self.contracts[label][case]['wire_sha256']:raise ValueError('Frozen wire drift before HTTP')
        body=body_bytes(wire['body']);expected=self.byte_contracts[label][case]
        if sha(body)!=expected:raise ValueError('Frozen HTTP bytes mismatch')
        return dict(slot=deepcopy(slot),request=request,url=wire['url'],body=body,body_sha256=expected,
                    wire_sha256=self.contracts[label][case]['wire_sha256'])

    def guard_http(self,prepared,request):
        slot=prepared['slot'];self.check_slot(slot);label=slot['config'];case=slot['case']
        frozen=self.saved[label][case]['wire']
        if request.method!='POST' or str(request.url)!=frozen['url']:raise ValueError('HTTP destination mismatch')
        if type(request.stream) is not httpx.ByteStream:raise ValueError('Outgoing HTTP bytes require an immutable repeatable stream')
        # Hash the stream that send() will consume, not a possibly stale _content cache.
        actual=b''.join(request.stream)
        if sha(actual)!=self.byte_contracts[label][case] or request.content!=actual:
            raise ValueError('Final outgoing HTTP bytes differ from frozen body')
        return True

    def require_activation(self):
        path=self.root/'artifacts/round-2b/quality/activation.json'
        if not self.execution_id or not path.is_file():raise ValueError('Quality activation missing')
        a=json.loads(path.read_text(encoding='utf-8'))
        if (a.get('execution_sha256')!=self.execution_id or a.get('input_sha256')!=self.input_id
                or a.get('owner_authorized') is not True or a.get('exclusive_local_api_window') is not True):
            raise ValueError('Quality activation does not match freeze')

    def source_guard(self):
        if self.execution_package is None:raise ValueError('Execution freeze not bound')
        verify_snapshot(self.root,self.execution_package,list(self.execution_package['files']))
        if source_inventory(self.root)!=self.execution_package['metadata']['source_inventory']:
            raise ValueError('Execution source inventory drift')

    @contextmanager
    def session(self,label,cfg):
        self.require_activation();self.source_guard()
        verify_model_binding(self.models[label],inventory(self.client))
        with loaded_model(self.client,cfg['model'],cfg['context_tokens'],expected_profile=self.profiles[label],expected_size=self.models[label]['bytes']) as echo:
            self.check_backend(label,echo);self.active_backend[label]=deepcopy(echo)
            try:yield echo
            finally:self.active_backend.pop(label,None)

    def send(self,client,slot,identity):
        self.require_activation();self.source_guard()
        label=slot['config'];cfg=self.configs[label]
        prepared=self.prepare(slot,echo=self.active_backend.get(label))
        if any(client.event_hooks.values()) or client.auth is not None:raise ValueError('Request hooks/auth middleware are not permitted')
        headers={'Content-Type':'application/json'}
        if cfg['provider']!='local':
            env={'google':'GOOGLE_API_KEY','anthropic':'ANTHROPIC_API_KEY'}[cfg['provider']]
            if not os.environ.get(env):raise ValueError('Missing API credential environment variable')
            if cfg['provider']=='google':headers['x-goog-api-key']=os.environ[env]
            else:headers.update({'x-api-key':os.environ[env],'anthropic-version':'2023-06-01'})
        outgoing=httpx.Request('POST',prepared['url'],content=prepared['body'],headers=headers,
                              extensions={'timeout':httpx.Timeout(cfg.get('timeout',300)).as_dict()})
        self.guard_http(prepared,outgoing)  # Before paid reservation or file side effects.
        paths=self.paths(slot);paths['request'].parent.mkdir(parents=True,exist_ok=True)
        if paths['request'].exists():
            if paths['request'].read_bytes()!=prepared['body']:raise ValueError('Saved outgoing bytes drift')
        else:paths['request'].write_bytes(prepared['body'])
        atomic_json(paths['request_meta'],{k:prepared[k] for k in ['slot','url','body_sha256','wire_sha256']})
        def perform():
            self.guard_http(prepared,outgoing)  # Last boundary immediately before send, no json= serialization.
            began=time.monotonic();response=client.send(outgoing,auth=None,follow_redirects=False)
            if response.status_code!=200:raise ProviderHTTPError(response.status_code)
            evidence=dict(raw_body_base64=base64.b64encode(response.content).decode())
            raw=None
            try:raw=response.json();normalized=normalize(raw,cfg['provider'])
            except (ValueError,KeyError,TypeError,IndexError):
                usage=raw.get('usageMetadata' if cfg['provider']=='google' else 'usage') if isinstance(raw,dict) else None
                return dict(status='invalid',error='Malformed provider envelope',rejection_codes=['malformed_provider_envelope'],
                    secondary_eligible=False,contract_defects=[],raw_response=raw,usage=usage if isinstance(usage,dict) else None,
                    seconds=time.monotonic()-began,**evidence)
            return dict(validate_response(normalized,prepared['request']),raw_response=raw,seconds=time.monotonic()-began,
                schema_deviations=self.saved[label][slot['case']]['wire']['schema_deviations'],**evidence)
        if cfg['provider']=='local':return perform()
        ledger=self.root/'artifacts/round-2/cloud-budget.sqlite'
        reserve=reserve_for_wire(cfg['model'],self.saved[label][slot['case']]['wire']);available=readonly_budget(ledger)
        return paid_call(ledger,'round2b-'+slot_id(slot),dict(identity,http_body_sha256=prepared['body_sha256'],execution=self.execution_id),
                         reserve,perform,lambda result:usage_cost(cfg['model'],result.get('usage')))

    def dry_run(self,folder,echoes=None):
        base=self.namespace_root();folder=Path(folder).resolve()
        if not folder.is_relative_to(base.resolve()) or folder.is_relative_to((base/'quality').resolve()):
            raise ValueError('Dry-run output must be isolated in round2b')
        if (folder/'report.json').exists():raise ValueError('Dry-run exists; do not overwrite')
        folder.mkdir(parents=True,exist_ok=True);records=[]
        for slot in self.schedule:
            p=self.prepare(slot,echo=(echoes or {}).get(slot['config']))
            request=httpx.Request('POST',p['url'],content=p['body']);self.guard_http(p,request)
            paths=self.paths(slot)
            records.append(dict(slot=slot,body_sha256=p['body_sha256'],actual_stream_sha256=sha(b''.join(request.stream)),wire_sha256=p['wire_sha256'],
                output={key:path.relative_to(self.root).as_posix() for key,path in paths.items()}))
        report=dict(slots=len(records),body_matches=len(records),http_calls=0,inference_calls=0,ledger_writes=0,records=records)
        atomic_json(folder/'report.json',report);return report

    def run(self,*,authorized=False,max_groups=None):
        if not authorized:raise ValueError('Quality run is not authorized')
        self.require_activation();self.source_guard()
        from dotenv import dotenv_values
        credentials=dotenv_values(self.root/'.env')
        for key in ['GOOGLE_API_KEY','ANTHROPIC_API_KEY']:
            value=os.environ.get(key) or credentials.get(key)
            if not value:raise ValueError('Missing API credential environment variable')
            os.environ[key]=value
        with httpx.Client(trust_env=False,auth=None,event_hooks={},transport=httpx.HTTPTransport(retries=0)) as client:
            self.client=client
            try:
                return execute_schedule(self.root/'artifacts/round-2b/quality',self.schedule,self.configs,self.execution_id,
                    lambda slot,identity:self.send(client,slot,identity),self.session,self.source_guard,authorized=True,max_groups=max_groups)
            finally:self.client=None


def load_input(root):
    root=Path(root);path=root/'docs/research/round2b/frozen-quality.json'
    package=json.loads(path.read_text(encoding='utf-8'))
    if package['snapshot_sha256']!=INPUT_SHA:raise ValueError('Input freeze is not the owner-approved snapshot')
    verify_snapshot(root,package,list(package['files']))
    if set(source_inventory(root))!=set(package['metadata']['source_inventory'])|ADDED_SOURCES:
        raise ValueError('Unreviewed additions beyond execution adapter')
    meta=package['metadata'];runtime_guard(meta);verify_external(meta['models']);verify_external(meta['environment'].get('installed_backend_binaries',{}))
    ledger=root/'artifacts/round-2/cloud-budget.sqlite';verify_ledger_anchor(ledger,meta['ledger'])
    if readonly_budget(ledger)<Decimal(meta['cloud_total_reserve']):raise ValueError('Insufficient frozen research budget')
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    q=root/'artifacts/round-2b/quality'
    adapter=Adapter(root,read(root/'docs/research/round2b/holdout-reviewed.json'),meta['configs'],
        (root/'docs/research/round2b/prompts/check-aprime-v1-uk.txt').read_text(encoding='utf-8'),
        read(q/'frozen-requests.json'),meta['contracts'],read(q/'schedule.json'),meta['native_load_profiles'],INPUT_SHA,meta['models'])
    if len(adapter.allowed_slots)!=720 or sum(len(v) for v in adapter.byte_contracts.values())!=240:raise ValueError('Incomplete execution contracts')
    return package,adapter


def probe_backend(root,output):
    _,adapter=load_input(root);output=Path(output)
    if output.exists():raise ValueError('Backend proof exists; never overwrite')
    echoes={}
    with httpx.Client(trust_env=False,timeout=15) as client:
        if any(r.get('loaded_instances') for r in inventory(client)):raise ValueError('GPU busy; do not unload owner models')
        for label,cfg in adapter.configs.items():
            if cfg['provider']!='local':continue
            verify_model_binding(adapter.models[label],inventory(client))
            with loaded_model(client,cfg['model'],cfg['context_tokens'],expected_profile=adapter.profiles[label],expected_size=adapter.models[label]['bytes']) as echo:
                adapter.check_backend(label,echo);echoes[label]=deepcopy(echo)
        if any(r.get('loaded_instances') for r in inventory(client)):raise ValueError('Owned backend session did not unload')
    output.parent.mkdir(parents=True,exist_ok=True)
    atomic_json(output,dict(input_sha256=INPUT_SHA,echoes=echoes,model_generation_calls=0,load_only=True,gpu_empty_after=True))
    return echoes


def build_execution_freeze(root):
    from round2.freeze import snapshot
    import subprocess
    root=Path(root);output=root/'docs/research/round2b/execution-freeze.json'
    if output.exists():raise ValueError('Execution freeze exists; never overwrite')
    if (root/'artifacts/round-2b/quality/activation.json').exists():raise ValueError('Activation must be absent during freeze')
    base,adapter=load_input(root)
    proofpath=root/'artifacts/round-2b/execution-preflight/backend-echo.json'
    drypath=root/'artifacts/round-2b/execution-dry-run/report.json'
    proof=json.loads(proofpath.read_text(encoding='utf-8'));dry=json.loads(drypath.read_text(encoding='utf-8'))
    local={label for label,cfg in adapter.configs.items() if cfg['provider']=='local'}
    if (proof.get('input_sha256')!=INPUT_SHA or set(proof['echoes'])!=local or not proof['load_only']
            or proof['model_generation_calls']!=0 or not proof['gpu_empty_after']):raise ValueError('Incomplete backend proof')
    for label,echo in proof['echoes'].items():adapter.check_backend(label,echo)
    if (dry['slots']!=720 or dry['body_matches']!=720 or any(dry[k]!=0 for k in ['http_calls','inference_calls','ledger_writes'])
            or [r['slot'] for r in dry['records']]!=adapter.schedule):raise ValueError('Incomplete dry-run proof')
    for r in dry['records']:
        slot=r['slot'];p=adapter.prepare(slot,echo=proof['echoes'].get(slot['config']))
        if (r['body_sha256']!=p['body_sha256'] or r['actual_stream_sha256']!=p['body_sha256']
                or r['wire_sha256']!=p['wire_sha256']
                or r['output']!={k:v.relative_to(adapter.root).as_posix() for k,v in adapter.paths(slot).items()}):
            raise ValueError('Dry-run bytes/output drift')
    paths=list(base['files'])+list(ADDED_SOURCES)+[
        'docs/research/round2b/frozen-quality.json','docs/superpowers/plans/2026-10-30-round2b-execution-freeze.md',
        proofpath.relative_to(root).as_posix(),drypath.relative_to(root).as_posix()]
    meta=dict(stage='round2b-execution-freeze',input_sha256=INPUT_SHA,source_inventory=source_inventory(root),
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        body_encoding='httpx-json-compact-order-preserved-v1;ensure_ascii=false;allow_nan=false',
        http_body_sha256=adapter.byte_contracts,approved_wire_contracts=base['metadata']['contracts'],
        guard='exact method/URL/slot envelope and final request stream bytes before each POST; no model substitution',
        output_root='artifacts/round-2b/quality',slots=720,distinct_wires=240,dry_run_http_calls=0,
        backend_echo_confirmed=sorted(local),backend_recheck='fresh exact qualification echo and frozen model ID in each live session',
        execution_harness_complete=True,quality_authorized=False,activated=False,
        activation_required=dict(path='artifacts/round-2b/quality/activation.json',execution_sha256='must equal this snapshot',
            input_sha256=INPUT_SHA,owner_authorized=True,exclusive_local_api_window=True),
        http_client=dict(trust_env=False,event_hooks=False,auth_middleware=False,transport_retries=0,follow_redirects=False),
        orchestration='unchanged primary execute_schedule; at most3local transport attempts recorded, uncertain paid calls never replay; no content retries',
        policies=deepcopy(base['metadata']['admission']),metrics=deepcopy(base['metadata']['metrics']),
        cloud_total_reserve=base['metadata']['cloud_total_reserve'],ledger=deepcopy(base['metadata']['ledger']))
    package=snapshot(root,paths,meta)
    with output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(package,stream,ensure_ascii=False,indent=2)
    return package


def load_execution(root):
    base,adapter=load_input(root);root=Path(root)
    package=json.loads((root/'docs/research/round2b/execution-freeze.json').read_text(encoding='utf-8'))
    verify_snapshot(root,package,list(package['files']))
    m=package['metadata']
    if m['input_sha256']!=INPUT_SHA or m['http_body_sha256']!=adapter.byte_contracts or m['quality_authorized'] or m['activated']:
        raise ValueError('Execution freeze contract drift')
    if m['source_inventory']!=source_inventory(root):raise ValueError('Execution source inventory drift')
    adapter.execution_id=package['snapshot_sha256'];adapter.execution_package=package
    return package,adapter
