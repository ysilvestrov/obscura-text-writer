"""Version4 task ordering and report construction, sharing legacy session controls."""
from ..impact.models import fingerprint
from . import planning4
from .models4 import SceneReport4
from .wire4 import classify_scoped


def next_search(repo,run,results,pinned):
    data=run.impact;plan=data['scene_plan']
    def missing(specs):
        return next((s for s in specs if s['id'] not in results),None)
    deltas=[pinned(s) for s in plan['delta_specs']]
    task=missing(deltas)
    if task:return task
    premises=[pinned(s) for s in planning4.premise_specs(repo,plan,results)]
    task=missing(premises)
    if task:return task
    def reduce(ids,phase):
        force=True
        while len(ids)>1 or force:
            out=[]
            for start in range(0,len(ids),2):
                spec=pinned(planning4.synthesis_spec(repo,plan,ids[start:start+2],results,phase))
                if spec['id'] not in results:return spec,None
                out.append(spec['id'])
            ids=out;force=False
        return None,ids
    roots=[]
    for material in sorted({t['material'] for t in plan['targets']}):
        premise_ids=[s['id'] for s in premises if s['material']==material]
        task,premise_roots=reduce(premise_ids,'premise_synthesis') if premise_ids else (None,[])
        if task:return task
        dependencies=[s['id'] for s in deltas]+premise_roots
        checks=[]
        for s in planning4.check_specs(repo,plan,results,dependencies):
            if s['material']==material:checks.append(pinned(s))
        task=missing(checks)
        if task:return task
        task,material_roots=reduce([s['id'] for s in checks],'synthesis')
        if task:return task
        roots.extend(material_roots)
    if len(data['specs'])>10000:raise ValueError('Пошук перевищив 10000 задач')
    data['roots']=roots
    return None


def make_report(run,results):
    data=run.impact;plan=data['scene_plan']
    candidates=list({fingerprint(c):c for r in results.values() for c in r.get('candidates',[])}.values())
    normalized=classify_scoped(candidates,plan)
    diagnostics=list({fingerprint([id,d]):dict(d,task_id=id) for id,r in results.items() for d in r.get('rejected',[])}.values())
    for diagnostic in normalized['rejected']:
        for task in data['roots']:
            if data['specs'][task].get('material')==diagnostic.get('material'):diagnostics.append(dict(diagnostic,task_id=task))
    partial=bool(diagnostics) or any(r['execution_state']!='complete' for r in results.values())
    return SceneReport4(story_id=run.story_id,scene_id=plan['scene_id'],run_id=run.id,targets=plan['targets'],
        complete=not partial,execution_state='partial' if partial else 'complete',concerns=normalized['concerns'],
        diagnostics=diagnostics,suppressed=normalized['suppressed'],statements=normalized['statements'],
        authority_revisions=plan['authority_revisions'],unresolved_task_ids=list(dict.fromkeys([*[id for id,r in results.items() if r['execution_state']!='complete'],*[d['task_id'] for d in diagnostics]])),registry=plan['registry'],part_specs=data['specs'],proofs=data['proofs'],
        coverage=dict(plan=plan,order=data['order'],roots=data['roots']))
