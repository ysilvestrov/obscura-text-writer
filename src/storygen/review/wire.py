"""Reconstruct exact request and normalize only task-local valid references."""
import json
from ..impact.models import fingerprint
from ..providers.models import RoleSettings
from ..providers.requests import generation_request,strict_schema
from .wire_models import DeltaResponse,CheckResponse


def compact(value):return len(json.dumps(value,ensure_ascii=False,separators=(',',':')))


def request_for(plan,spec,results):
    if plan.get('contract_version')==4:
        from .wire4 import request_for as request4
        return request4(plan,spec,results)
    refs=list(dict.fromkeys(spec['source_refs']+spec['target_refs']))
    rules=[]
    for result in results.values():
        for rule in result['changes']:
            if rule['id'] in spec.get('rule_ids',[]):rules.append(rule)
    for rule in rules:refs.extend(rule['source_refs'])
    refs=list(dict.fromkeys(refs));registry=plan['registry']
    changes=sorted({registry[id]['change_id'] for id in refs if registry[id]['kind']=='source'})
    change_alias={id:'C'+str(i+1) for i,id in enumerate(changes)}
    aliases={};evidence={}
    for i,id in enumerate(refs):
        row=registry[id];alias=('T' if row['kind']=='target' else 'S')+str(i+1);aliases[alias]=id
        evidence[alias]=dict(kind=row['kind'],text=row['text'],**({'side':row['side'],'change':change_alias[row['change_id']],'label':row['label'],'field':row['field']} if row['kind']=='source' else {'material':row['material']}))
    reverse={id:alias for alias,id in aliases.items()}
    payload=dict(phase=spec['phase'],response_character_limit=plan['result_cap'],evidence=evidence)
    if 'basis_modes' in plan:
        payload['review_basis']={alias:plan['basis_modes'][registry[id]['version_id']] for alias,id in aliases.items() if registry[id]['kind']=='target'}
        if 'current_consistency' in payload['review_basis'].values():payload['basis_note']='Історична база цього тексту невідома. Перевірте узгодженість із поточними передумовами; не вигадуйте його історію створення.'
    if spec['phase']!='delta':
        payload['current_rules']=[dict(change=change_alias.get(rule['change_ref'],rule['change_ref']),current=rule['current'],retired=rule['current'] is None,retired_statement=rule['before'] if rule['current'] is None else None,source_refs=[reverse[id] for id in rule['source_refs']]) for rule in rules]
        payload['children']=[dict(has_concerns=bool(results[id]['concerns'])) for id in spec['dependencies'] if id in results and results[id]['phase']!='delta']
    model=DeltaResponse if spec['phase']=='delta' else CheckResponse
    schema=strict_schema(model)
    source=[k for k,v in evidence.items() if v['kind']=='source'];target=[k for k,v in evidence.items() if v['kind']=='target']
    def limit(node,values):
        node['items']={'type':'string','enum':values} if values else {'type':'string'}
        if not values:node['maxItems']=0
    c=schema['$defs']['WireConcern']['properties']
    limit(c['change_refs'],list(change_alias.values()));limit(c['source_refs'],source);limit(c['target_refs'],target)
    # Enforce an actual aggregate wire budget by limiting bounded rows, not 100 proof receipts.
    count=max(1,min(4,(plan['result_cap']-256)//1100))
    if model is DeltaResponse:
        d=schema['$defs']['WireChange']['properties'];d['change_ref']={'type':'string','enum':list(change_alias.values())}
        limit(d['before_refs'],[k for k in source if evidence[k]['side']=='old']);limit(d['source_refs'],[k for k in source if evidence[k]['side']=='new'])
        schema['properties']['changes']['maxItems']=count;schema['properties']['questions']['maxItems']=count
    else:
        limit(schema['properties']['carry_refs'],list(aliases));schema['properties']['concerns']['maxItems']=count
    payload['response_schema']=schema if spec['settings']['provider']['response_mode']!='json_schema' else None
    role=RoleSettings.model_validate(spec['settings'])
    body=generation_request('impact_part',role,spec['system'],json.dumps(payload,ensure_ascii=False,separators=(',',':')),{'impact_wire_schema':schema})
    return payload,body,aliases


def validate_part(raw,plan,spec,results):
    if plan.get('contract_version')==4:
        from .wire4 import validate_part as validate4
        return validate4(raw,plan,spec,results)
    model=DeltaResponse if spec['phase']=='delta' else CheckResponse
    parsed=model.model_validate(raw)
    if not parsed.complete:raise ValueError('Пошук частини незавершено; збережені зауваження доступні, автоматичного повтору немає')
    if compact(raw)>plan['result_cap']:raise ValueError('Відповідь пошуку перевищила резерв; текст збережено')
    payload,body,aliases=request_for(plan,spec,results);registry=plan['registry']
    change_alias={row['change']:registry[aliases[id]]['change_id'] for id,row in payload['evidence'].items() if row['kind']=='source'}
    def refs(values,kind=None,side=None):
        if len(values)!=len(set(values)):raise ValueError('Повтор посилання пошуку')
        out=[]
        for alias in values:
            if alias not in aliases:raise ValueError('Невідоме посилання пошуку')
            row=registry[aliases[alias]]
            if kind and row['kind']!=kind or side and row.get('side')!=side:raise ValueError('Посилання іншого типу або сторони')
            out.append(aliases[alias])
        return out
    changes=[];concerns=[];carry=[]
    for dep in spec['dependencies']:
        if dep not in results:raise ValueError('Немає результату дочірньої частини')
        if spec['phase']=='synthesis':concerns.extend(results[dep]['concerns'])
    if model is DeltaResponse:
        for value in parsed.changes:
            if value.change_ref not in change_alias:raise ValueError('Невідома зміна передумов')
            old=refs(value.before_refs,'source','old');new=refs(value.source_refs,'source','new');cid=change_alias[value.change_ref]
            if value.before is None and value.current is None:raise ValueError('Порожня зміна передумов')
            if value.before is not None and not old or value.current is not None and not new:raise ValueError('Зміна без доказів належної сторони')
            if any(registry[id]['change_id']!=cid for id in old+new):raise ValueError('Докази іншої зміни')
            data=dict(change_ref=cid,before=value.before,current=value.current,before_refs=old,source_refs=new or old)
            changes.append(dict(id=fingerprint(data),**data))
        items=parsed.questions
        if any(item.kind!='question' for item in items):raise ValueError('Дельта повернула вердикт про сцену')
    else:items=parsed.concerns;carry=refs(parsed.carry_refs)
    for item in items:
        source=refs(item.source_refs,'source');target=refs(item.target_refs,'target')
        if item.kind=='issue' and (not source or not target):raise ValueError('Зауваження не має source/target доказу')
        if any(id not in change_alias for id in item.change_refs):raise ValueError('Невідома передумова зауваження')
        data=dict(kind=item.kind,message=item.message,change_refs=[change_alias[id] for id in item.change_refs],source_refs=source,target_refs=target)
        concerns.append(dict(id=fingerprint(data),**data))
    concerns=list({x['id']:x for x in concerns}.values())
    return dict(phase=spec['phase'],complete=True,changes=changes,concerns=concerns,carry_refs=carry)
