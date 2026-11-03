"""Sequential frozen research dispatch. Lifecycle/HTTP dependencies are injected."""
from contextlib import nullcontext
from itertools import groupby
import json
from pathlib import Path

from .runner import run_slot,atomic_json,digest


def slot_id(slot):
    suffix='-warmup' if slot.get('warmup') else ''
    if slot.get('reload') is not None:suffix+=f"-reload{slot['reload']}"
    return f"{slot.get('phase','quality')}-{slot['config']}-{slot['case']}-d{slot['draw']}{suffix}"


def timing_schedule(cases,configs):
    if len(cases)!=8:raise ValueError('Timing requires the eight original dev cases')
    result=[]
    for block,(label,cfg) in enumerate(configs.items()):
        if cfg['provider']!='local':continue
        for index,case in enumerate([cases[0],*cases]):
            result.append(dict(phase='timing',case=case['id'],config=label,draw=1,block=block,warmup=index==0))
    return result


def cached(folder,slot,identity):
    path=Path(folder)/'slots'/(slot_id(slot)+'.json')
    if not path.is_file():return False
    state=json.loads(path.read_text(encoding='utf-8'))
    if state['identity']!=digest(identity):raise ValueError('Frozen identity mismatch')
    if 'result' in state and state.get('result_sha256')!=digest(state['result']):raise ValueError('Saved result checksum mismatch')
    return 'result' in state


def execute_schedule(folder,schedule,configs,frozen_id,send,session,guard,*,authorized=False,max_groups=None):
    """Resume complete slots without loading GPU or invoking send again.

    No retry after invalid/refusal/length. Paid uncertain transport blocks on the
    first attempt; native local transport alone keeps the existing three bound.
    Each group owns its loaded model; finally unload also runs after a failure.
    """
    if not authorized:raise ValueError('Quality not authorized')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);completed=0;groups=0
    for (_,label),items in groupby(schedule,key=lambda s:(s['block'],s['config'])):
        guard();slots=list(items);cfg=configs[label]
        def identity(slot):return dict(phase=slot.get('phase','quality'),freeze=frozen_id,slot=slot,config=cfg)
        needed=any(not cached(folder,s,identity(s)) for s in slots)
        if needed and max_groups is not None and groups>=max_groups:break
        context=session(label,cfg) if needed and cfg['provider']=='local' else nullcontext({})
        with context as load:
            if needed:
                groups+=1
                prefix=f"load-b{slots[0]['block']}-{label}"
                epoch=len(list(folder.glob(prefix+'-session*.json')))+1
                atomic_json(folder/f"{prefix}-session{epoch}.json",load)
                if slots[0].get('phase')=='timing' and cached(folder,slots[0],identity(slots[0])):
                    warmup=dict(slots[0],reload=epoch)
                    guard()
                    run_slot(folder/'slots',slot_id(warmup),identity(warmup),
                             lambda:send(warmup,identity(warmup)),authorized=True)
            for slot in slots:
                ident=identity(slot)
                def perform():
                    guard()
                    return send(slot,ident)
                result=run_slot(folder/'slots',slot_id(slot),ident,perform,authorized=True,
                                retry_transport=cfg['provider']=='local')
                if cfg['provider']=='local' and (result.get('reasoning_tokens')!=0 or result.get('reasoning_chars')!=0):
                    raise ValueError('Local reasoning not proven off; saved result retained')
                completed+=1
                atomic_json(folder/'progress.json',dict(completed=completed,total=len(schedule),last=slot,
                            frozen_id=frozen_id,new_groups=groups))
    return dict(completed=completed,total=len(schedule),new_groups=groups)


def frozen_send(client,root,cases,configs,contracts,*,gpu,instances=None):
    from .cloud import paid_call,usage_cost
    from .freeze import reserve_for_wire,readonly_budget
    from .requests import build_request
    from .transports import dispatch,envelope
    root=Path(root)
    def send(slot,identity):
        cfg=configs[slot['config']];provider=cfg['provider'];case=cases[slot['case']]
        request=build_request(case,cfg);wire=envelope(request['body'],provider,cfg)
        if digest(wire)!=contracts[slot['config']][case['id']]['wire_sha256']:
            raise ValueError('Frozen native wire changed')
        phase=slot.get('phase','quality')
        if phase not in {'quality','timing'} or phase=='timing' and provider!='local':raise ValueError('Invalid research phase')
        folder=root/f'artifacts/round-2/{phase}/requests';folder.mkdir(parents=True,exist_ok=True)
        if provider=='local':
            instance=(instances or {}).get(slot['config'])
            if not instance:raise ValueError('No verified owned local instance')
            dispatch_cfg=dict(cfg,model=instance)
            actual=envelope(request['body'],provider,dispatch_cfg)
            atomic_json(folder/(slot_id(slot)+'.json'),dict(actual,canonical_wire_sha256=digest(wire),verified_instance=instance))
            before=gpu()
            result=dispatch(client,request,provider,dispatch_cfg,authorized=True)
            # Sampling is labelled; not a continuously observed peak VRAM.
            result['gpu_before']=before;result['gpu_after']=gpu()
        else:
            atomic_json(folder/(slot_id(slot)+'.json'),wire)
            ledger=root/'artifacts/round-2/cloud-budget.sqlite';reserve=reserve_for_wire(cfg['model'],wire)
            available=readonly_budget(ledger)
            result=paid_call(ledger,slot_id(slot),dict(identity,wire=digest(wire)),reserve,
                lambda:dispatch(client,request,provider,cfg,authorized=True,reserve=reserve,available=available),
                lambda res:usage_cost(cfg['model'],res.get('usage')))
        print(json.dumps(dict(slot=slot_id(slot),status=result['status'],seconds=result.get('seconds')),ensure_ascii=False),flush=True)
        return result
    return send
