"""Immutable one-scene search geometry. Every passage is delivered without truncation."""
import json
from importlib.resources import files
from ..impact.models import fingerprint
from .capture import plan_review,modes_for
from ..authoring.blueprints import get_role_settings
from ..token_budget.service import token_estimate
from .wire import request_for
from ..language import load_prompt


def stamp(spec):return fingerprint({k:v for k,v in spec.items() if k!='id'})


def make_spec(plan,phase,sources=(),targets=(),dependencies=(),rules=()):
    spec=dict(phase=phase,source_refs=list(sources),target_refs=list(targets),dependencies=list(dependencies),rule_ids=list(rules),settings=plan['settings'],system=plan['system'])
    spec['id']=stamp(spec)
    return spec


def measurement(repo,plan,spec,results):
    _,body,_=request_for(plan,spec,results)
    role=spec['settings'];provider=role['provider']
    prediction=token_estimate(repo,provider['provider'],provider['base_url'],body)
    if plan.get('local_token_counter') and provider['provider']=='local':
        from ..token_budget.local_profiles import load_counter
        from ..token_budget.local_counter import predict_body,CounterUnavailable
        try:prediction.update(predict_body(body,load_counter(repo.root,plan['local_token_counter'],verify_bytes=True)))
        except (CounterUnavailable,KeyError,OSError,TypeError):prediction['reasons']=['local_counter_unavailable']
    chars=len(json.dumps(body,ensure_ascii=False,separators=(',',':')))
    return body,prediction,chars


def fits(repo,plan,spec,results):
    _,estimate,chars=measurement(repo,plan,spec,results);role=spec['settings']
    return estimate['input_tokens']<=role['context_tokens']-role['max_output_tokens'] and chars<=role['max_input_chars']


def packed(repo,plan,phase,sources,targets,results,dependencies=(),rules=()):
    if phase=='check':
        changes={plan['registry'][id]['change_id'] for id in sources}
        rules=[r['id'] for value in results.values() for r in value['changes'] if r['change_ref'] in changes]
    spec=make_spec(plan,phase,sources,targets,dependencies,rules)
    if fits(repo,plan,spec,results):return [spec]
    # Split the Cartesian rectangle, never drop a source/target pair.
    which=sources if len(sources)>=len(targets) and len(sources)>1 else targets
    if len(which)<=1:raise ValueError('Навіть мінімальна частина пошуку не вміщується в ліміти планувальника')
    middle=len(which)//2;out=[]
    for half in [which[:middle],which[middle:]]:
        out+=packed(repo,plan,phase,half if which is sources else sources,half if which is targets else targets,results,dependencies,rules)
    if len(out)>10000:raise ValueError('Пошук потребує понад 10000 частин')
    return out


def registry_for(targets):
    registry={}
    def add(text,**owner):
        # Code-owned addresses have overlap; the model returns only short aliases.
        for start in range(0,max(1,len(text)),448):
            row=dict(**owner,start=start,end=min(len(text),start+512),text=text[start:start+512],document_hash=fingerprint(text))
            registry[fingerprint(row)]=row
    changes={}
    for target in targets:
        add(target['text'],kind='target',material=target['material'],version_id=target['version_id'])
        for c in target['changes']:changes[c['id']]=c
    for c in changes.values():
        for side in ['old','new']:add(c[side+'_text'],kind='source',side=side,change_id=c['id'],changed=c['changed'],label=c['label'],field=c['input_field'],
            author_label=c['input_kind'] in {'scene','head'} or c['input_kind']=='order' and c['owner_id']!=targets[0]['story_id'])
    return registry


def prepare_scene(repo,scene_id,contract_version=3):
    if contract_version==4:
        from .planning4 import prepare_scene as prepare4
        return prepare4(repo,scene_id)
    scene=repo.get_scene(scene_id);view=repo.context_view(scene.story_id)
    targets=[t for t in plan_review(view).targets if t.scene_id==scene_id]
    if any(t.blockers for t in targets):raise ValueError('; '.join('Сцена '+str(t.position+1)+' «'+t.scene_title+'» · '+('завдання' if t.material=='brief' else 'проза')+': '+', '.join(dict.fromkeys(t.blockers)) for t in targets if t.blockers))
    role=get_role_settings(repo,scene.story_id)['planner']
    plan=dict(story_id=scene.story_id,scene_id=scene_id,targets=[t.model_dump() for t in targets],basis_modes=modes_for(view,targets),settings=role.model_dump(),
        system=load_prompt('review_part_v3',view.story.language),
        result_cap=min(6000,role.max_output_tokens//2),registry=registry_for([t.model_dump() for t in targets]))
    if plan['result_cap']<256:raise ValueError('Замалий резерв відповіді пошуку')
    from ..token_budget.local_profiles import select_snapshot
    body=request_for(plan,make_spec(plan,'check'),{})[1]
    plan['local_token_counter']=select_snapshot(repo.root,role.provider.provider,role.provider.base_url,body)
    plan['id']=fingerprint(plan)
    changed=[id for id,r in plan['registry'].items() if r['kind']=='source' and r['changed']]
    plan['delta_specs']=packed(repo,plan,'delta',changed,[],{}) if changed else []
    return plan


def check_specs(repo,plan,results):
    if plan.get('contract_version')==4:
        from .planning4 import check_specs as check4
        return check4(repo,plan,results)
    sources=[id for id,r in plan['registry'].items() if r['kind']=='source' and r['side']=='new']
    rules=[r['id'] for value in results.values() for r in value['changes']]
    deps=[id for id,value in results.items() if value['phase']=='delta']
    specs=[]
    for target in plan['targets']:
        refs=[id for id,r in plan['registry'].items() if r['kind']=='target' and r['version_id']==target['version_id']]
        specs+=packed(repo,plan,'check',sources,refs,results,deps,rules)
    return specs


def synthesis_spec(repo,plan,children,results):
    if plan.get('contract_version')==4:
        from .planning4 import synthesis_spec as synthesis4
        return synthesis4(repo,plan,children,results)
    refs=list(dict.fromkeys(id for child in children for id in results[child]['carry_refs']))
    sources=[id for id in refs if plan['registry'][id]['kind']=='source']
    targets=[id for id in refs if plan['registry'][id]['kind']=='target']
    spec=make_spec(plan,'synthesis',sources,targets,children)
    if not fits(repo,plan,spec,results):raise ValueError('Зведення частин не вміщується; попередні результати збережено')
    return spec


def validate_coverage(plan,specs):
    if plan.get('contract_version')==4:
        from .planning4 import validate_coverage as validate4
        return validate4(plan,specs)
    reg=plan['registry'];delta=set();pairs=set();seen_targets=set()
    for s in specs:
        if s['id']!=stamp(s):raise ValueError('Змінено ідентичність частини')
        if any(id not in reg for id in s['source_refs']+s['target_refs']):raise ValueError('Невідоме джерело частини')
        if s['phase']=='delta':delta.update(s['source_refs'])
        if s['phase']=='check':
            seen_targets.update(s['target_refs']);pairs.update((a,b) for a in s['source_refs'] for b in s['target_refs'])
    required_delta={id for id,r in reg.items() if r['kind']=='source' and r['changed']}
    sources={id for id,r in reg.items() if r['kind']=='source' and r['side']=='new'}
    targets={id for id,r in reg.items() if r['kind']=='target'}
    if delta!=required_delta or seen_targets!=targets or pairs!={(a,b) for a in sources for b in targets}:raise ValueError('Неповне покриття передумов або тексту')


def premise_specs(repo,plan,results):
    from .planning4 import premise_specs as premises4
    return premises4(repo,plan,results)
