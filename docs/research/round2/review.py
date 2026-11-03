"""Research human review: common fact panel and separately retained blind key."""
from collections import Counter
from copy import deepcopy
import random


def shared_tp_panel(records,*,seed):
    """Select before owner review; cover ceil(TP facts /5) for every model.

    Order is case/draw/fact, shuffled by a dedicated recorded seed. Adding a
    unit counts its coverage for ALL models; no model-specific sample panels.
    """
    if not records:raise ValueError('No primary measurements')
    by_slot={};models=sorted({r['config'] for r in records});totals=Counter()
    for r in records:
        if r.get('pending') or r.get('outcome') is None or r.get('measurement')=='secondary':
            raise ValueError('Panel requires completed primary adjudication')
        key=(r['case'],r['draw'],r['config'])
        if key in by_slot or len(set(r['tp_ids']))!=len(r['tp_ids']):raise ValueError('Duplicate slot/fact')
        by_slot[key]=r;totals[r['config']]+=len(r['tp_ids'])
    pairs={(r['case'],r['draw']) for r in records}
    if any((*pair,m) not in by_slot for pair in pairs for m in models):raise ValueError('Missing model response')
    units=sorted({(r['case'],r['draw'],f) for r in records for f in r['tp_ids']})
    random.Random(seed).shuffle(units)
    quotas={m:(totals[m]+4)//5 for m in models};covered=dict.fromkeys(models,0);selected=[]
    for case,draw,fact in units:
        found={m:fact in by_slot[(case,draw,m)]['tp_ids'] for m in models}
        if not any(found[m] and covered[m]<quotas[m] for m in models):continue
        selected.append(dict(case=case,draw=draw,fact=fact,
            responses=[deepcopy(by_slot[(case,draw,m)]) for m in models]))
        for m in models:covered[m]+=int(found[m])
        if all(covered[m]>=quotas[m] for m in models):break
    if any(covered[m]<quotas[m] for m in models):raise ValueError('Panel coverage not met')
    return dict(seed=seed,quotas=quotas,covered=covered,units=selected,models=models)


def blind_export(panel,responses,*,seed,cases=None):
    models=list(panel['models']);random.Random(seed).shuffle(models)
    key={f'M{i+1:02d}':m for i,m in enumerate(models)}
    reverse={m:alias for alias,m in key.items()};units=[]
    for unit in panel['units']:
        shown=[]
        for row in sorted(unit['responses'],key=lambda r:reverse[r['config']]):
            reply=responses[(unit['case'],unit['draw'],row['config'])]
            shown.append(dict(model=reverse[row['config']],text=reply.get('text',''),
                              status=reply['status'],owner_adjudication=None))
        entry=dict(case=unit['case'],draw=unit['draw'],fact=unit['fact'],responses=shown)
        if cases is not None:entry['example']=deepcopy(cases[unit['case']])
        units.append(entry)
    return dict(units=units,review='owner',blind=True),key


def secondary_form(records):
    return [dict(case=r['case'],draw=r['draw'],config=r['config'],
                 response=deepcopy(r['response']),
                 executor_adjudication=deepcopy(r.get('executor_adjudication')),owner_adjudication=None)
            for r in records if r['response'].get('secondary_eligible') is True]


def executor_form(records,cases,*,seed):
    responses={};pairs={}
    for row in records:
        key=(row['case'],row['draw'],row['config'])
        if key in responses:raise ValueError('Duplicate response slot')
        responses[key]=row['response'];pairs.setdefault(key[:2],[]).append(row)
    panel=dict(models=sorted({r['config'] for r in records}),units=[
        dict(case=c,draw=d,fact=None,responses=rows) for (c,d),rows in sorted(pairs.items())])
    form,key=blind_export(panel,responses,seed=seed,cases=cases)
    form['review']='executor'
    for unit in form['units']:
        for reply in unit['responses']:
            reply.pop('owner_adjudication');reply['executor_adjudication']=None
    return form,key


def adjudicate_form(form,key,records,cases):
    from .scoring import classify_call,classify_secondary
    from .report import model_verdict
    original={(r['case'],r['draw'],r['config']):r['response'] for r in records}
    if len(original)!=len(records):raise ValueError('Duplicate original slots')
    if len(set(key.values()))!=len(key) or set(key.values())!={r['config'] for r in records}:
        raise ValueError('Blind key participant mismatch')
    decisions={}
    for unit in form['units']:
        for reply in unit['responses']:
            slot=(unit['case'],unit['draw'],key[reply['model']])
            if slot in decisions or slot not in original:raise ValueError('Duplicate/unknown form slot')
            raw=original[slot]
            if reply['text']!=raw.get('text','') or reply['status']!=raw['status']:
                raise ValueError('Original response changed in form')
            decision=reply.get('executor_adjudication')
            if not isinstance(decision,dict) or type(decision.get('content_refusal')) is not bool:
                raise ValueError('Missing explicit executor adjudication')
            decisions[slot]=decision
    if set(decisions)!=set(original):raise ValueError('Missing form adjudication slots')
    primary=[];secondary=[]
    for (case,draw,config),raw in original.items():
        decision=decisions[(case,draw,config)];gold=cases[case]['gold']
        classified=classify_call(raw,gold,decision)
        if classified['pending']:raise ValueError('Pending semantic adjudication')
        metadata=dict(case=case,draw=draw,config=config)
        primary.append(dict(classified,**metadata,context=cases[case]['context'],
                            verdict='refusal' if classified['outcome']=='refusal' else model_verdict(raw)))
        if raw.get('secondary_eligible'):
            secondary.append(dict(classify_secondary(raw,gold,decision),**metadata))
    return primary,secondary


def apply_owner_panel(panel,form,key,records,responses,cases):
    """Import exact frozen fact panel; repeated slots must have identical decisions."""
    from .runner import digest
    from .scoring import classify_call
    if shared_tp_panel(records,seed=panel['seed'])!=panel:raise ValueError('Panel differs from seeded executor TP selection')
    expected={(u['case'],u['draw'],u['fact']) for u in panel['units']}
    seen=set();decisions={};models=set(panel['models'])
    if set(key.values())!=models or len(key)!=len(models):raise ValueError('Blind key mismatch')
    for unit in form['units']:
        identity=(unit['case'],unit['draw'],unit['fact'])
        if identity in seen or identity not in expected:raise ValueError('Owner panel unit mismatch')
        seen.add(identity);shown=set()
        for reply in unit['responses']:
            config=key[reply['model']]
            if config in shown:raise ValueError('Duplicate owner response')
            shown.add(config);slot=(unit['case'],unit['draw'],config);raw=responses[slot]
            if reply['text']!=raw.get('text','') or reply['status']!=raw['status']:raise ValueError('Owner response evidence changed')
            decision=reply.get('owner_adjudication')
            if not isinstance(decision,dict) or type(decision.get('content_refusal')) is not bool:
                raise ValueError('Owner adjudication required for every panel response')
            if slot in decisions and decisions[slot]!=decision:raise ValueError('Conflicting owner decisions for repeated slot')
            decisions[slot]=decision
        if shown!=models:raise ValueError('Missing owner model response')
    if seen!=expected:raise ValueError('Incomplete owner panel')
    updated=[];history=[]
    for row in records:
        slot=(row['case'],row['draw'],row['config'])
        if slot not in decisions:updated.append(deepcopy(row));continue
        decision=decisions[slot];result=classify_call(responses[slot],cases[row['case']]['gold'],decision)
        if result['pending']:raise ValueError('Pending owner judgement')
        final=dict(row,**result,owner_reviewed=True)
        if result['outcome']=='refusal':final['verdict']='refusal'
        updated.append(final)
        history.append(dict(case=slot[0],draw=slot[1],config=slot[2],executor_classification=deepcopy(row),
                            owner_adjudication=deepcopy(decision),owner_classification=deepcopy(final)))
    audit=dict(completed=True,panel_sha256=digest(panel),form_sha256=digest(form),
               executor_primary_sha256=digest(records),final_primary_sha256=digest(updated),decisions=history,
               secondary_candidate_slots=[list(k) for k,v in sorted(responses.items()) if v.get('secondary_eligible') is True])
    return updated,audit
