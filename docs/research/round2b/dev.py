"""A-prime v1 dev only. No new holdout authoring or prompt activation."""
from copy import deepcopy
from collections import Counter
import json
from pathlib import Path

from round2.requests import build_request
from round2.runner import digest,atomic_json,run_slot
from round2.freeze import source_inventory,verify_snapshot,reserve_for_wire,readonly_budget,ledger_anchor,verify_ledger_anchor
from round2.transports import envelope,dispatch
from round2.cloud import paid_call,usage_cost
from round2.local_models import inventory,loaded_model
from round2b.spike import file_sha,verify_model_binding

LABELS=('C1','C2','L3','L5','L6')
RULE='Якщо чинні передумови суперечать одна одній і жодна не має авторського пріоритету, а target спирається на спірний факт, поверни `question` із запитом, яку передумову вважати правильною. Відповідність target одній із таких передумов не є `issue`. `issue` — тільки суперечність однозначно встановленій передумові. Твердження target про стан канону не є передумовою.'

def dev_cases(root):
    old=json.loads((Path(root)/'docs/research/round2/holdout.json').read_text(encoding='utf-8'))
    out=[c for c in old if c['family']!='D']
    for theme,source,target,priority in [
        ('time','У каноні є дві картки початку зустрічі: картка А вказує 10:00, картка Б — 17:00. Обидві стосуються початку тієї самої зустрічі в один день.',
         'О десятій Олена відчинила двері студії для гостей, і зустріч почалася.',
         'Автор надав пріоритет картці А: зустріч починається о 10:00. Картка Б є відкинутою чернеткою.'),
        ('injury','Дві картки канону описують одну травму Олени: у картці А ушкоджена права щиколотка, у картці Б — ліва. Записи стосуються одного стану в той самий момент.',
         'Олена наклала пов’язку на ушкоджену праву щиколотку й підсунула під ногу подушку.',
         'Автор визначив картку А чинною: ушкоджена права щиколотка. Картка Б є відкинутою чернеткою.')]:
        for verdict in ['question','clean']:
            sources=['Олені 30 років. Вона готує виставку фотографій.',source]
            if verdict=='clean':sources.append(priority)
            out.append(dict(id=f'dev2b-D-{theme}-{verdict}',family='D',theme=theme,sources=sources,target=target,
                            gold=dict(verdict=verdict,contradictions=[]),dev_only=True,exclude_from_holdout_2b=True))
    if len(out)!=44:raise ValueError('Expected40 old non-D and4 new D')
    return out

def ap_request(case,config,prompt):
    request=build_request(case,config)
    request['plan']['system']=prompt;request['body']['messages'][0]['content']=prompt
    return request

def content_counts(rows,cases):
    statuses=Counter(r['status'] for r in rows)
    result=dict(calls=len(rows),valid=statuses['valid'],invalid=statuses['invalid'],refusal=statuses['refusal'],
                clean_calls=0,clean_with_concerns=0,clean_strict_fp=0,clean_invalid=0,
                question_calls=0,question_as_issue=0,question_empty=0,question_only=0,question_unreadable=0,issue_calls=0,issue_empty=0)
    for r in rows:
        verdict=cases[r['case']]['gold']['verdict']
        try:
            concerns=json.loads(r.get('text') or 'null')['concerns']
            if not isinstance(concerns,list):concerns=None
        except (ValueError,TypeError,KeyError):concerns=None
        if verdict=='clean':
            result['clean_calls']+=1;result['clean_with_concerns']+=bool(concerns)
            result['clean_strict_fp']+=r['status']=='valid' and bool(concerns)
            result['clean_invalid']+=r['status']=='invalid'
        elif verdict=='question':
            result['question_calls']+=1;result['question_empty']+=concerns==[]
            readable=concerns is not None and all(isinstance(c,dict) and isinstance(c.get('kind'),str) and c['kind'] in {'issue','question'} for c in concerns)
            result['question_unreadable']+=not readable
            kinds={c['kind'] for c in concerns} if readable else set()
            result['question_as_issue']+='issue' in kinds
            result['question_only']+=kinds=={'question'}
        else:
            result['issue_calls']+=1;result['issue_empty']+=concerns==[]
    return result

def verify_manifest(root,m):
    if digest({k:v for k,v in m.items() if k!='sha256'})!=m.get('sha256'):raise ValueError('Dev manifest checksum changed')
    verify_snapshot(root,m['original'],list(m['original']['files']))
    if source_inventory(root)!=m['source_inventory']:raise ValueError('Dev source inventory changed')
    for path,sha in m['files'].items():
        if file_sha(Path(root)/path)!=sha:raise ValueError('Dev file drift: '+path)
    verify_ledger_anchor(Path(root)/'artifacts/round-2/cloud-budget.sqlite',m['ledger_anchor'])

def prepare(root,folder):
    root=Path(root);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'manifest.json').exists():raise ValueError('Iteration already prepared; never overwrite')
    read=lambda path:json.loads((root/path).read_text(encoding='utf-8'))
    original=read('docs/research/round2/frozen-primary.json');verify_snapshot(root,original,list(original['files']))
    cases=dev_cases(root);base=root/'src/storygen/generation/resources/review_part_uk_v3.txt'
    prompt=base.read_text(encoding='utf-8').rstrip()+'\n'+RULE+'\n'
    promptpath=root/'docs/research/round2b/prompts/check-aprime-v1-uk.txt';promptpath.parent.mkdir(exist_ok=True)
    if promptpath.exists() and promptpath.read_text(encoding='utf-8')!=prompt:raise ValueError('Candidate prompt changed; new iteration required')
    promptpath.write_text(prompt,encoding='utf-8',newline='\n')
    configs={k:deepcopy(original['metadata']['configs'][k]) for k in LABELS}
    registry=read('artifacts/round-2/preflight/model-links.json');models={}
    for label in ['L3','L5','L6']:
        model=deepcopy(original['metadata']['models'][label]);p=Path(model['path'])
        if not p.is_file() or file_sha(p)!=model['sha256']:raise ValueError('Weight SHA changed: '+label)
        registered=registry['links'].get(label,model['path'])
        publisher='round2-r28l' if label in registry['links'] else p.parts[p.parts.index('models')+1]
        models[label]=dict(model,key=configs[label]['model'],registered_path=registered,publisher=publisher)
    source=source_inventory(root);added=set(source)-set(original['files'])
    allowed={'docs/research/round2b/spike.py','docs/research/round2b/test_spike.py','docs/research/r28m-spike.py',
             'docs/research/round2b/dev.py','docs/research/round2b/test_dev.py','docs/research/r28n-aprime-dev.py'}
    if added!=allowed:raise ValueError('Unexpected source additions')
    files=allowed|{promptpath.relative_to(root).as_posix(),'docs/research/2026-10-29-round-2b-codex-brief.md',
                   'docs/research/2026-10-29-round-2b-holdout-rebuild-plan.md','artifacts/round-2/preflight/model-links.json'}
    contracts={};reserves={};day='2026-10-29'
    for label,cfg in configs.items():
        contracts[label]={};amount=0
        for case in cases:
            req=ap_request(case,cfg,prompt);wire=envelope(req['body'],cfg['provider'],cfg)
            contracts[label][case['id']]=digest(wire)
            if cfg['provider']!='local':amount+=reserve_for_wire(cfg['model'],wire,day=day)
        if cfg['provider']!='local':reserves[label]=str(amount)
    from decimal import Decimal
    ledger=root/'artifacts/round-2/cloud-budget.sqlite'
    verify_ledger_anchor(ledger,original['metadata']['ledger'])
    current_anchor=ledger_anchor(ledger)
    total=sum(map(Decimal,reserves.values()));available=readonly_budget(ledger)
    if total>available:raise ValueError('Full dev reserve exceeds shared budget')
    m=dict(stage='round2b-aprime-dev',iteration=1,original=original,configs=configs,models=models,cases=cases,
           prompt=prompt,prompt_sha256=__import__('hashlib').sha256(prompt.encode('utf-8')).hexdigest(),
           source_inventory=source,files={p:file_sha(root/p) for p in sorted(files)},contracts=contracts,
           profiles={k:original['metadata']['native_load_profiles'][k] for k in models},tariff_day=day,
           reserves=reserves,total_reserve=str(total),available_before=str(available),ledger_anchor=current_anchor,calls=220,cloud_calls=88,
           excluded_from_holdout_2b=[c['id'] for c in cases if c.get('dev_only')],
           oracle_policy='No tuning participant or measured future senior may serve as model oracle.',
           note='Initial candidate only; do not freeze A-prime or create holdout2b until owner review.')
    m['sha256']=digest(m);atomic_json(folder/'manifest.json',m)
    return m

def execute(root,folder,client,*,authorized=False):
    if not authorized:raise ValueError('A-prime dev not authorized')
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
                            paid=db.execute('SELECT identity,result FROM calls WHERE id=?',(f'round2b-dev-v1-{label}-{case["id"]}',)).fetchone()
                        if not paid or paid[0]!=digest(identity) or paid[1] is None or json.loads(paid[1])!=state['result']:
                            raise ValueError('Completed paid checkpoint missing from ledger; reconcile before resume')
                    continue
            if cfg['provider']!='local':outstanding+=reserve_for_wire(cfg['model'],wire)
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
                    return paid_call(ledger,f'round2b-dev-v1-{label}-{case["id"]}',identity,reserve,
                        lambda:dispatch(client,req,cfg['provider'],cfg,authorized=True,reserve=reserve,available=available),
                        lambda result:usage_cost(cfg['model'],result.get('usage')))
                result=run_slot(folder/'slots',f'{label}-{case["id"]}',identity,send,authorized=True,retry_transport=local)
                rows.append(dict(result,label=label,case=case['id']))
                counts={k:content_counts([r for r in rows if r['label']==k],cases) for k in LABELS}
                atomic_json(folder/'progress.json',dict(completed=len(rows),total=220,label=label,last=case['id'],counts=counts))
                print(json.dumps(dict(completed=len(rows),label=label,case=case['id'],status=result['status'],seconds=result.get('seconds')),ensure_ascii=False),flush=True)
                if local and (result.get('reasoning_tokens')!=0 or result.get('reasoning_chars')!=0):raise ValueError('Local reasoning not proven off')
    atomic_json(folder/'summary.json',counts)
    return counts
