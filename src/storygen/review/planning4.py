"""Measured pairwise source coverage, including the diagonal, for contract4."""
from importlib.resources import files
from itertools import combinations_with_replacement
from ..impact.models import fingerprint
from . import planning as legacy
from ..language import load_prompt


def registry_for(targets):
    reg=legacy.registry_for(targets)
    changes={c['id']:c for t in targets for c in t['changes']}
    for row in reg.values():
        if row['kind']=='source':
            c=changes[row['change_id']]
            row['version_id']=c.get(row['side']+'_ref') or fingerprint([c['id'],row['side'],row['document_hash']])
    return reg


def prepare_scene(repo,scene_id):
    plan=legacy.prepare_scene(repo,scene_id)
    plan.pop('id');plan.pop('delta_specs')
    plan.update(contract_version=4,classifier_version=1,registry=registry_for(plan['targets']),
        system=load_prompt('review_part_v4',repo.get_story(plan['story_id']).language),
        priorities=[],statements={},authority_revisions={})
    # Storage command is installed with the authority package; an empty registry is valid.
    if hasattr(repo,'review'):
        from ..storage import review_authority
        snapshot=review_authority.snapshot(repo,plan['story_id'],scene_id)
        plan.update(snapshot)
        view=repo.context_view(plan['story_id'])
        for material in ['brief','prose']:
            ids={id for d in plan['priorities'] if d['material']==material for id in [d['preferred_statement_id'],d['superseded_statement_id']]}
            if ids:review_authority._live_statements(view,scene_id,material,[plan['statements'][id] for id in ids])
    from ..token_budget.local_profiles import select_snapshot
    body=legacy.request_for(plan,legacy.make_spec(plan,'check'),{})[1]
    plan['local_token_counter']=select_snapshot(repo.root,plan['settings']['provider']['provider'],plan['settings']['provider']['base_url'],body)
    plan['id']=fingerprint(plan)
    changed=[id for id,r in plan['registry'].items() if r['kind']=='source' and r['changed']]
    plan['delta_specs']=packed(repo,plan,'delta',changed,[],{}) if changed else []
    for spec in plan['delta_specs']:
        spec['material']=None;spec['id']=legacy.stamp(spec)
    # Materialize all geometry at preflight to bound the quadratic expansion.
    if sum(initial_counts(repo,plan).values())>10000:raise ValueError('Пошук потребує понад 10000 частин і зведень')
    return plan


def packed(repo,plan,phase,sources,targets,results,dependencies=()):
    spec=legacy.make_spec(plan,phase,sources,targets,dependencies)
    if legacy.fits(repo,plan,spec,results):return [spec]
    # Premise pairs are indivisible: splitting would silently lose the comparison.
    if phase=='premise_check':raise ValueError('Пара передумов не вміщується в ліміти планувальника')
    which=sources if len(sources)>=len(targets) and len(sources)>1 else targets
    if len(which)<=1:raise ValueError('Мінімальна частина пошуку не вміщується в ліміти планувальника')
    middle=len(which)//2;out=[]
    for half in [which[:middle],which[middle:]]:
        out.extend(packed(repo,plan,phase,half if which is sources else sources,half if which is targets else targets,results,dependencies))
    if len(out)>10000:raise ValueError('Пошук потребує понад 10000 частин')
    return out


def reduction_count(count):
    if not count:return 0
    total=0
    while True:
        count=(count+1)//2;total+=count
        if count==1:return total


def initial_counts(repo,plan):
    premises=premise_specs(repo,plan,{});checks=check_specs(repo,plan,{})
    materials={t['material'] for t in plan['targets']}
    return dict(delta=len(plan['delta_specs']),premise=len(premises),check=len(checks),
        premise_synthesis=sum(reduction_count(sum(s['material']==m for s in premises)) for m in materials),
        synthesis=sum(reduction_count(sum(s['material']==m for s in checks)) for m in materials))


def premise_specs(repo,plan,results):
    refs=[id for id,r in plan['registry'].items() if r['kind']=='source' and r['side']=='new']
    materials=sorted({t['material'] for t in plan['targets']})
    out=[]
    for material in materials:
        # A fitting group delivers all pair comparisons in one call. Partition only
        # when the serialized body does not fit, preserving cross-group pairs.
        full=legacy.make_spec(plan,'premise_check',refs,[])
        full['material']=material
        if legacy.fits(repo,plan,full,results):groups=[refs]
        else:
            groups=[];current=[]
            # Bound preflight work as well as dispatched tasks for pathological inputs.
            if len(refs)*(len(refs)+1)//2>100000:raise ValueError('Надто багато пар передумов для безпечного preflight')
            covered=set()
            for a,b in combinations_with_replacement(refs,2):
                if tuple(sorted([a,b])) in covered:continue
                proposed=list(dict.fromkeys([*current,a,b]))
                test=legacy.make_spec(plan,'premise_check',proposed,[]);test['material']=material
                if not legacy.fits(repo,plan,test,results):
                    if current:
                        groups.append(current);covered.update(tuple(sorted(p)) for p in combinations_with_replacement(current,2))
                    current=list(dict.fromkeys([a,b]))
                    test=legacy.make_spec(plan,'premise_check',current,[]);test['material']=material
                    if not legacy.fits(repo,plan,test,results):raise ValueError('Пара передумов не вміщується в ліміти планувальника')
                else:current=proposed
                if len(groups)>10000:raise ValueError('Пошук потребує понад 10000 задач')
            if current:groups.append(current)
        for group in groups:
            spec=legacy.make_spec(plan,'premise_check',group,[])
            spec.update(material=material,premise_pairs=[list(p) for p in combinations_with_replacement(group,2)])
            spec['id']=legacy.stamp(spec);out.append(spec)
    return out


def check_specs(repo,plan,results,premise_roots=()):
    sources=[id for id,r in plan['registry'].items() if r['kind']=='source' and r['side']=='new']
    specs=[]
    for target in plan['targets']:
        refs=[id for id,r in plan['registry'].items() if r['kind']=='target' and r['version_id']==target['version_id']]
        for spec in packed(repo,plan,'check',sources,refs,results,premise_roots):
            spec['material']=target['material'];spec['id']=legacy.stamp(spec);specs.append(spec)
    return specs


def synthesis_spec(repo,plan,children,results,phase='synthesis'):
    refs=list(dict.fromkeys(r for child in children for r in results[child]['carry_refs']))
    spec=legacy.make_spec(plan,phase,[r for r in refs if plan['registry'][r]['kind']=='source'],[r for r in refs if plan['registry'][r]['kind']=='target'],children)
    materials={results[c].get('material') for c in children}
    if len(materials)>1:raise ValueError('Зведення змішує області авторського пріоритету')
    spec['material']=next(iter(materials),None);spec['id']=legacy.stamp(spec)
    if not legacy.fits(repo,plan,spec,results):raise ValueError('Зведення доказів не вміщується; попередні результати збережено')
    return spec


def validate_coverage(plan,specs):
    if len(specs)>10000:raise ValueError('Понад 10000 задач')
    reg=plan['registry'];sources={r for r,row in reg.items() if row['kind']=='source' and row['side']=='new'}
    targets={r for r,row in reg.items() if row['kind']=='target'};premises=set();pairs=set();seen=set();delta=set()
    for spec in specs:
        if spec['id']!=legacy.stamp(spec):raise ValueError('Змінено ідентичність частини')
        if any(r not in reg for r in spec['source_refs']+spec['target_refs']):raise ValueError('Невідоме джерело частини')
        if spec['phase']=='premise_check':
            if spec['target_refs'] or not spec['source_refs'] or not set(spec['source_refs'])<=sources:raise ValueError('Некоректна пара передумов')
            expected=[list(p) for p in combinations_with_replacement(spec['source_refs'],2)]
            if spec.get('premise_pairs')!=expected:raise ValueError('Підроблене покриття пар передумов')
            premises.update((spec.get('material'),*sorted([a,b])) for a,b in expected)
        if spec['phase']=='delta':delta.update(spec['source_refs'])
        if spec['phase']=='check':
            if not set(spec['source_refs'])<=sources or not set(spec['target_refs'])<=targets:raise ValueError('Неправильні ролі частини')
            seen.update(spec['target_refs']);pairs.update((a,b) for a in spec['source_refs'] for b in spec['target_refs'])
    if premises!={(material,*sorted([a,b])) for material in {t['material'] for t in plan['targets']} for a,b in combinations_with_replacement(sources,2)}:raise ValueError('Неповне покриття пар передумов')
    if seen!=targets or pairs!={(a,b) for a in sources for b in targets}:raise ValueError('Неповне покриття target')
    if delta!={r for r,row in reg.items() if row['kind']=='source' and row['changed']}:raise ValueError('Неповна дельта')
