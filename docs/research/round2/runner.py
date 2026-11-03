"""Offline-testable scheduling and durable slots; no model management implementation."""
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import random
import time

import httpx
from .transports import ProviderHTTPError


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def make_schedule(case_ids: list[str], config_ids: list[str], seed: int, draws: int) -> list[dict]:
    if not case_ids or not config_ids or len(set(case_ids))!=len(case_ids) or len(set(config_ids))!=len(config_ids) or draws<1:
        raise ValueError('Invalid schedule dimensions')
    rng=random.Random(seed);out=[];block=0
    for draw in range(1,draws+1):
        cases=list(case_ids);rng.shuffle(cases)
        for start in range(0,len(cases),8):
            rotation=block%len(config_ids);configs=config_ids[rotation:]+config_ids[:rotation]
            for config in configs:
                for case in cases[start:start+8]:out.append(dict(case=case,config=config,draw=draw,block=block,seed=seed))
            block+=1
    return out


def atomic_json(path,value):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w',encoding='utf-8',newline='\n') as file:
        json.dump(value,file,ensure_ascii=False,indent=2);file.flush();os.fsync(file.fileno())
    os.replace(temp,path)


def run_slot(folder,slot: str,identity: dict,send,*,authorized=False,reserve=0,available=0,retry_transport=True) -> dict:
    """One worker only. send() returns an already validated result, never raw auth headers.

    Uncertain in-flight calls require manual reconciliation; they are not blindly replayed.
    Retry bound of three total attempts is a frozen research policy, not SDK behavior.
    Budget here is a per-call guard, not a whole-experiment ledger (later stage).
    """
    if not authorized:raise ValueError('Call is not authorized')
    if not slot or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in slot):raise ValueError('Unsafe slot ID')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);path=folder/(slot+'.json');stamp=digest(identity)
    state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(identity=stamp,attempts=[],inflight=False)
    if state['identity']!=stamp:raise ValueError('Frozen identity mismatch')
    if 'result' in state:
        if state.get('result_sha256')!=digest(state['result']):raise ValueError('Saved result checksum mismatch')
        return state['result']
    if state.get('blocked'):raise ValueError('Provider HTTP/uncertain transport error requires owner decision before resume')
    if state['inflight']:raise ValueError('Previous dispatch uncertain; reconcile before resume')
    if Decimal(str(reserve))<0 or Decimal(str(available))<Decimal(str(reserve)):raise ValueError('Insufficient budget')
    while len(state['attempts'])<3:
        state['inflight']=True;atomic_json(path,state);began=time.monotonic()
        try:
            result=send()
            if result.get('status') not in {'valid','invalid','refusal'}:raise ValueError('Invalid dispatch result')
        except ProviderHTTPError as exc:
            attempt=dict(status='transport',error_type=type(exc).__name__,http_status=exc.status_code,
                         rejection_codes=['provider_http_error'])
            state['blocked']=True
        except httpx.TransportError as exc:
            # Exception text may contain full URLs/headers/credentials; never persist it.
            attempt=dict(status='transport',error_type=type(exc).__name__,rejection_codes=['transport_error'])
            if not retry_transport:state['blocked']=True
        else:
            attempt=dict(status=result['status'],rejection_codes=result.get('rejection_codes',[]))
            state['result']=result;state['result_sha256']=digest(result)
        attempt.update(attempt=len(state['attempts'])+1,seconds=round(time.monotonic()-began,6))
        state['attempts'].append(attempt);state['inflight']=False;atomic_json(path,state)
        if state.get('blocked'):raise ValueError('Provider HTTP/uncertain transport error; owner decision required before resume')
        if 'result' in state:return state['result']
    raise ValueError('Transport retries exhausted; owner decision required')


@contextmanager
def model_session(snapshot,restore):
    original=snapshot()
    try:yield original
    finally:restore(original)
