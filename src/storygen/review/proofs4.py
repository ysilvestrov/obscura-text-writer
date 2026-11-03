"""Offline exact replay of candidate, authority and coverage derivation."""
from ..impact.models import fingerprint
from .planning4 import registry_for,validate_coverage
from .proofs import verify_part


def verify_report(report,attempts,read_partial):
    plan=report.coverage['plan'];order=report.coverage['order'];roots=report.coverage['roots']
    from .capture import validate_basis
    validate_basis(plan)
    if plan.get('contract_version')!=4 or plan.get('classifier_version')!=1:raise ValueError('Невідомий контракт доказів')
    if plan['id']!=fingerprint({k:v for k,v in plan.items() if k not in {'id','delta_specs'}}):raise ValueError('Змінений план пошуку')
    if (plan['story_id']!=report.story_id or plan['scene_id']!=report.scene_id or plan['targets']!=[t.model_dump() for t in report.targets]
        or plan['registry']!=registry_for(plan['targets']) or report.registry!=plan['registry']):raise ValueError('Змінені джерела звіту')
    if len(order)!=len(set(order)) or set(order)!=set(report.proofs) or set(order)!=set(report.part_specs):raise ValueError('Неповний граф')
    if report.authority_revisions!=plan['authority_revisions']:raise ValueError('Змінена ревізія авторських рішень')
    results={};reachable=set()
    for id in order:
        spec=report.part_specs[id]
        if spec['system']!=plan['system'] or any(dep not in results for dep in spec['dependencies']):raise ValueError('Змінений або циклічний граф')
        results[id]=verify_part(attempts[report.proofs[id]],plan,spec,results,read_partial,report.story_id,report.run_id)
    validate_coverage(plan,list(report.part_specs.values()))
    def visit(id):
        if id in reachable:return
        reachable.add(id)
        for dep in report.part_specs[id]['dependencies']:visit(dep)
    if not roots or any(id not in results or report.part_specs[id]['phase']!='synthesis' for id in roots):raise ValueError('Немає фінального зведення')
    for id in roots:visit(id)
    if reachable!=set(order):raise ValueError('Частина не включена до фінального графа')
    # Check tasks require all premise leaves for their own author-decision scope.
    for id in order:
        spec=report.part_specs[id]
        if spec['phase']!='check':continue
        closure=set()
        def deps(key):
            if key in closure:return
            closure.add(key)
            for dep in report.part_specs[key]['dependencies']:deps(dep)
        deps(id)
        required={k for k in order if report.part_specs[k]['phase']=='premise_check' and report.part_specs[k]['material']==spec['material']}
        if not required<=closure:raise ValueError('Перевірка target втратила premise proofs')
    from .runner4 import make_report
    from types import SimpleNamespace
    replay=make_report(SimpleNamespace(story_id=report.story_id,id=report.run_id,
        impact=dict(scene_plan=plan,specs=report.part_specs,proofs=report.proofs,order=order,roots=roots)),results)
    if replay.model_dump(exclude={'id','created_at'})!=report.model_dump(exclude={'id','created_at'}):raise ValueError('Звіт не відповідає первинним доказам')
    return results
