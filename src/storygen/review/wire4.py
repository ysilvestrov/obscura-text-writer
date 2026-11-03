"""Version4 request and independently validated candidate normalization."""
from copy import deepcopy
from ..providers.models import RoleSettings
from ..providers.requests import generation_request,strict_schema
from .contract4 import CheckResponse4,DeltaResponse4
from .evidence import classify_candidates
from .wire import compact


def request_for(plan,spec,results):
    refs=list(dict.fromkeys(spec['source_refs']+spec['target_refs']))
    for child in spec['dependencies']:
        for ref in results.get(child,{}).get('carry_refs',[]):
            if spec['phase'] in {'synthesis','premise_synthesis'} and ref not in refs:refs.append(ref)
    aliases={('S' if plan['registry'][ref]['kind']=='source' else 'T')+str(i+1):ref for i,ref in enumerate(refs)}
    reverse={v:k for k,v in aliases.items()}
    evidence={alias:dict(kind=plan['registry'][ref]['kind'],text=plan['registry'][ref]['text'],
        side=plan['registry'][ref].get('side'),statement_origin=plan['registry'][ref]['version_id'],
        change_ref=plan['registry'][ref].get('change_id'),field=plan['registry'][ref].get('field'),label=plan['registry'][ref].get('label')) for alias,ref in aliases.items()}
    schema=strict_schema(DeltaResponse4 if spec['phase']=='delta' else CheckResponse4)
    # The same fixed row limit is enforced by Pydantic and both wire modes;
    # the independent serialized-character cap still bounds the full response.
    schema['properties']['candidates']['maxItems']=0 if spec['phase']=='delta' else 4
    if spec['phase']=='delta':schema['properties']['changes']['maxItems']=4
    priorities=[]
    for decision in plan.get('priorities',[]):
        if decision.get('material')!=spec.get('material'):continue
        priorities.append({**decision,'preferred':plan['statements'][decision['preferred_statement_id']],
                          'superseded':plan['statements'][decision['superseded_statement_id']]})
    payload=dict(contract_version=4,phase=spec['phase'],response_character_limit=plan['result_cap'],evidence=evidence,
        author_priorities=priorities,review_basis=plan.get('basis_modes',{}),material=spec.get('material'),
        children=[dict(analysis_status=results[id]['analysis_status'],execution_state=results[id]['execution_state']) for id in spec['dependencies'] if id in results])
    inherited=[c for id in spec['dependencies'] for c in results.get(id,{}).get('candidates',[]) if c.get('_material')==spec.get('material')]
    authority=classify_scoped(inherited,plan)
    unresolved={id for pair in authority['conflicts'] for id in pair}
    superseded={d['superseded_statement_id'] for d in plan.get('priorities',[]) if d['material']==spec.get('material')}
    payload['premise_authority']=[dict(statement=s,status='superseded' if id in superseded else 'unresolved' if id in unresolved else 'current')
        for id,s in authority['statements'].items() if s['role']=='source' and (id in unresolved or id in superseded or any(id==d['preferred_statement_id'] for d in plan.get('priorities',[]) if d['material']==spec.get('material')))]
    available={plan['registry'][id].get('change_id') for id in refs}
    payload['current_rules']=[dict(change_ref=c['change_ref'],current=c['current'],retired=c['current'] is None,retired_statement=c['before'] if c['current'] is None else None)
        for result in results.values() for c in result.get('changes',[]) if c['change_ref'] in available]
    payload['response_schema']=schema if spec['settings']['provider']['response_mode']!='json_schema' else None
    body=generation_request('impact_part',RoleSettings.model_validate(spec['settings']),spec['system'],
        __import__('json').dumps(payload,ensure_ascii=False,separators=(',',':')),{'impact_wire_schema':schema})
    return payload,body,aliases


def validate_part(raw,plan,spec,results):
    model=DeltaResponse4 if spec['phase']=='delta' else CheckResponse4
    parsed=model.model_validate(raw,strict=True)
    payload,_,aliases=request_for(plan,spec,results)
    if len(parsed.candidates)>4 or spec['phase']=='delta' and len(parsed.changes)>4:raise ValueError('Перевищено кількість рядків контракту')
    if compact(raw)>plan['result_cap']:raise ValueError('Відповідь пошуку перевищила резерв; текст збережено')
    from .contract4 import Contradiction
    candidates=[];diagnostics=[];changes=[]
    for index,item in enumerate(parsed.candidates):
        data=item.model_dump()
        try:
            names=['left','right'] if isinstance(item,Contradiction) else ['target']
            for name in names:data[name]['ref']=aliases[data[name]['ref']]
            if 'source_refs' in data:data['source_refs']=[aliases[id] for id in data['source_refs']]
            # Preserve per-candidate scope even when the global report has more refs.
            checked=classify_candidates([data],{id:plan['registry'][id] for id in aliases.values()},[],statements={})
            if checked['rejected']:raise ValueError(checked['rejected'][0]['reason'])
            if any(plan['registry'][data[n]['ref']].get('side')=='old' for n in names):raise ValueError('Історичне твердження не є чинною передумовою')
            if spec['phase'] in {'delta','premise_check','premise_synthesis'} and any(s['role']=='target' for s in checked['statements'].values()):raise ValueError('Фаза передумов не перевіряє target')
            data['_material']=spec.get('material');candidates.append(data)
        except (ValueError,KeyError,TypeError) as exc:diagnostics.append(dict(index=index,code='invalid_evidence',reason=str(exc)))
    if spec['phase']=='delta':
        # Use exact task-local old/new addresses; the model never creates authority.
        for c in parsed.changes:
            old=[aliases[id] for id in c.before_refs];new=[aliases[id] for id in c.source_refs]
            rows=plan['registry'];allowed_changes={rows[id]['change_id'] for id in aliases.values()}
            if c.change_ref not in allowed_changes:raise ValueError('Невідома зміна передумов')
            if c.before is None and c.current is None:raise ValueError('Порожня зміна передумов')
            if c.before is not None and not old or c.current is not None and not new:raise ValueError('Зміна без доказів')
            if any(rows[id]['kind']!='source' or rows[id]['side']!='old' or rows[id]['change_id']!=c.change_ref for id in old):raise ValueError('Неправильний old доказ')
            if any(rows[id]['kind']!='source' or rows[id]['side']!='new' or rows[id]['change_id']!=c.change_ref for id in new):raise ValueError('Неправильний new доказ')
            changes.append(dict(change_ref=c.change_ref,before=c.before,current=c.current,before_refs=old,source_refs=new or old))
    inherited=[]
    for child in spec['dependencies']:
        if child not in results:raise ValueError('Немає доказу попередньої частини')
        inherited.extend(results[child].get('candidates',[]))
        diagnostics.extend(results[child].get('rejected',[]))
        if results[child]['execution_state']!='complete':diagnostics.append(dict(code='incomplete_dependency',task_id=child))
    # Canonical candidate IDs preserve child results without trusting model synthesis.
    from ..impact.models import fingerprint
    all_candidates=list({fingerprint(c):c for c in [*inherited,*candidates]}.values())
    out=classify_scoped(all_candidates,plan)
    out['rejected']=diagnostics+out['rejected']
    if parsed.analysis_status=='unable':out['rejected'].append(dict(code='analysis_unable',reason=parsed.reason))
    out.update(phase=spec['phase'],material=spec.get('material'),analysis_status=parsed.analysis_status,complete=not out['rejected'],
        execution_state='partial' if out['rejected'] else 'complete',changes=changes,candidates=all_candidates,
        carry_refs=list(dict.fromkeys(r for c in all_candidates for r in ([c['left']['ref'],c['right']['ref']] if c['type']=='contradiction' else [c['target']['ref'],*c['source_refs']]))))
    return out


def classify_scoped(candidates,plan):
    out=dict(concerns=[],suppressed=[],rejected=[],statements=dict(plan.get('statements',{})),conflicts=[])
    from ..impact.models import fingerprint
    for material in sorted({c.get('_material') for c in candidates},key=str):
        scoped=[c for c in candidates if c.get('_material')==material]
        if material not in {'brief','prose'}:
            if scoped:out['rejected'].append(dict(code='invalid_scope',reason='Немає області твердження'))
            continue
        current=classify_candidates(scoped,plan['registry'],[d for d in plan.get('priorities',[]) if d['material']==material],statements=plan.get('statements',{}))
        out['statements'].update(current['statements'])
        for key in ['concerns','suppressed','rejected','conflicts']:
            if key=='concerns':
                for c in current[key]:c.update(material=material,id=fingerprint([material,c['id']]))
            elif key in {'suppressed','rejected'}:
                for c in current[key]:c['material']=material
            out[key].extend(current[key])
    out['execution_state']='partial' if out['rejected'] else 'complete'
    return out
