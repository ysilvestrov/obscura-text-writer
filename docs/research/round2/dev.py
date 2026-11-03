"""Opt-in local dev only. Eight published round-one cases, never holdout."""
import argparse
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
import subprocess

import httpx

from .local_models import inventory, loaded_model
from .requests import build_request
from .runner import atomic_json, digest, run_slot
from .transports import dispatch, envelope


def old_cases():
    path=Path(__file__).resolve().parents[1]/'r28k-base-model-probe.py'
    spec=importlib.util.spec_from_file_location('round1_dev_cases',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return [dict(id=label,sources=[source],target=text,expected_issue=expected)
            for label,expected,source,text in module.CASES]


def qualification_error(label,result):
    if result['status']!='valid':return 'invalid/refusal: inspect raw response before further dev'
    if result.get('reasoning_tokens')!=0 or result.get('reasoning_chars')!=0:
        return 'Local reasoning not proven off: actual token telemetry must equal zero'
    if label in {'L3','L4'} and result['seconds']>60:return '12B short dev exceeded 60 seconds; owner decision required'
    return None


def stop_after(label,result,complete_dev=False):
    if not qualification_error(label,result):return False
    # Owner approval 29 Oct only permits finishing old dev after invalid results.
    # It never permits a refusal retry, reasoning leak, or excessive 12B latency.
    if not complete_dev or result['status']!='invalid':return True
    return (result.get('reasoning_tokens')!=0 or result.get('reasoning_chars')!=0 or
            label in {'L3','L4'} and result['seconds']>60)


def gpu_snapshot():
    result=subprocess.run(['nvidia-smi','--query-gpu=name,memory.used,memory.total,utilization.gpu',
                           '--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
    return result.stdout.strip()


def cloud_dev_reserve(request,provider,config):
    if (provider,config['model']) not in {('google','gemini-3.5-flash-lite'),('anthropic','claude-haiku-5-5')}:
        raise ValueError('Only approved lower-tier dev participants')
    wire=envelope(request['body'],provider,config)
    if len(json.dumps(wire['body'],ensure_ascii=False).encode('utf-8'))>16000:
        raise ValueError('Dev request exceeds reserved input bound')
    # <=16K wire bytes plus schema/system accounting margin, <=4096 output incl thinking.
    # $0.05 is above even 100K input +4096 output on either selected Standard tariff.
    return Decimal('0.05')


def run_cloud(label):
    from .cloud import paid_call, balance, usage_cost
    from dotenv import dotenv_values
    import os
    root=Path(__file__).resolve().parents[3]
    manifest=json.loads((root/'docs/research/round2/manifest.json').read_text(encoding='utf-8'))
    if manifest['harness_frozen'] or not manifest['cloud_budget_approved'] or manifest['cloud_budget_usd']!='10.00':
        raise ValueError('Cloud dev gate not met')
    expected={'C1':('google','gemini-3.5-flash-lite','GOOGLE_API_KEY'),
              'C2':('anthropic','claude-haiku-5-5','ANTHROPIC_API_KEY')}
    provider,model,key_env=expected[label]
    if manifest['cloud_models'][label]!={'provider':provider,'model':model}:raise ValueError('Cloud identity changed')
    key=os.environ.get(key_env) or dotenv_values(root/'.env').get(key_env)
    if not key:raise ValueError('Missing cloud key')
    os.environ[key_env]=key
    config=dict(model=model,schema_relaxation_approved=True,timeout=300)
    usage_cost(model,{})  # Expired tariff stops before reserving or calling.
    db=root/'artifacts/round-2/cloud-budget.sqlite';folder=root/'artifacts/round-2/dev'/label
    folder.mkdir(parents=True,exist_ok=True);records=[]
    prepared=[(case,build_request(case,config)) for case in old_cases()]
    reserves=[cloud_dev_reserve(request,provider,config) for _,request in prepared]
    if balance(db)<sum(reserves):raise ValueError('Insufficient shared budget for full dev series')
    print(json.dumps(dict(config=label,maximum_series_reserve=str(sum(reserves)),shared_available=str(balance(db)))),flush=True)
    with httpx.Client(trust_env=False) as client:
        for (case,request),reserve in zip(prepared,reserves,strict=True):
            wire=envelope(request['body'],provider,config)
            atomic_json(folder/(case['id']+'-request.json'),wire)
            identity=dict(phase='dev',model=model,wire=digest(wire))
            result=paid_call(db,label+'-dev-'+case['id'],identity,reserve,
                lambda:dispatch(client,request,provider,config,authorized=True,reserve=reserve,available=reserve),
                lambda res:usage_cost(model,res.get('usage')))
            atomic_json(folder/(case['id']+'-response.json'),result)
            record=dict(case=case['id'],status=result['status'],seconds=result['seconds'],
                reasoning_tokens=result.get('reasoning_tokens'),shared_available=str(balance(db)))
            records.append(record);atomic_json(folder/'results.json',records)
            print(json.dumps(record,ensure_ascii=False),flush=True)
            if result['status']!='valid':return 2  # No repair/content retry; inspect before freeze.
    return 0


def run_local(label,key,context,complete_dev=False):
    root=Path(__file__).resolve().parents[3];folder=root/'artifacts/round-2/dev'/label
    manifest=json.loads((root/'docs/research/round2/manifest.json').read_text(encoding='utf-8'))
    if manifest['harness_frozen']:raise ValueError('Dev configuration changes forbidden after freeze')
    folder.mkdir(parents=True,exist_ok=True);records=[]
    config=dict(model=key,context_tokens=context,timeout=300)
    with httpx.Client(trust_env=False) as client:
        before=inventory(client);atomic_json(folder/'inventory-before.json',before)
        try:
            with loaded_model(client,key,context) as loaded:
                atomic_json(folder/'load.json',loaded);atomic_json(folder/'gpu-loaded.json',gpu_snapshot())
                for case in old_cases():
                    request=build_request(case,config)
                    atomic_json(folder/(case['id']+'-request.json'),request['body'])
                    identity=dict(request=digest(request['body']),model=key,load=loaded['load_config'],phase='dev')
                    result=run_slot(folder/'slots',case['id'],identity,
                        lambda:dispatch(client,request,'local',config,authorized=True),authorized=True)
                    stop=qualification_error(label,result)
                    record=dict(case=case['id'],status=result['status'],seconds=result['seconds'],
                                reasoning_tokens=result.get('reasoning_tokens'),reasoning_chars=result.get('reasoning_chars'),
                                stop=stop,gpu=gpu_snapshot())
                    records.append(record);atomic_json(folder/'results.json',records)
                    print(json.dumps(record,ensure_ascii=False),flush=True)
                    if stop_after(label,result,complete_dev):break
        finally:
            atomic_json(folder/'inventory-after.json',inventory(client))
    if len(records)!=8 or any(r['status']!='valid' for r in records):return 2
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',choices=['L1','L2','L3','L4','L5','L6','C1','C2'],required=True)
    parser.add_argument('--model')
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--complete-dev',action='store_true',help='Owner-approved completion of old dev; never repairs/repeats cached replies')
    args=parser.parse_args();context=32768 if args.label in {'L3','L4'} else 131072
    if not args.run:
        print(f'Prepared {len(old_cases())} old dev cases; no inference');return 0
    if args.label in {'C1','C2'}:return run_cloud(args.label)
    if not args.model:raise ValueError('Local model key required')
    return run_local(args.label,args.model,context,args.complete_dev)


if __name__=='__main__':raise SystemExit(main())
