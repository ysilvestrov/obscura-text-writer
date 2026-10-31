"""Replay authority from original raw answers and exact transmitted requests."""
from ..impact.validation import decode_response
from .wire import request_for,validate_part
from .planning import validate_coverage,stamp,registry_for


def verify_part(attempt,plan,spec,results,read_partial,story_id,run_id):
    if (attempt.story_id!=story_id or attempt.run_id!=run_id or attempt.scene_id!=plan['scene_id'] or
        attempt.stage!='review_part' or attempt.state!='completed' or attempt.finish_reason!='stop' or
        spec['id']!=stamp(spec) or attempt.context.get('review_spec')!=spec or attempt.context.get('review_plan_id')!=plan['id']):
        raise ValueError('Непридатний доказ пошуку')
    if attempt.context.get('api_request')!=request_for(plan,spec,results)[1]:raise ValueError('Запит доказу не відповідає частині')
    parsed=validate_part(decode_response(read_partial(attempt.partial_path)),plan,spec,results)
    if parsed!=attempt.context.get('review_result'):raise ValueError('Результат доказу змінено')
    return parsed


def verify_report(report,attempts,read_partial):
    plan=report.coverage['plan'];order=report.coverage['order'];roots=report.coverage['roots']
    from .capture import validate_basis
    validate_basis(plan)
    if plan['registry']!=registry_for(plan['targets']):raise ValueError('Уривки не відповідають повним джерелам')
    if plan['story_id']!=report.story_id or plan['scene_id']!=report.scene_id or plan['registry']!=report.registry or plan['targets']!=[t.model_dump() for t in report.targets]:raise ValueError('Звіт не відповідає плану')
    from ..impact.models import fingerprint
    if plan['id']!=fingerprint({k:v for k,v in plan.items() if k not in {'id','delta_specs'}}):raise ValueError('Змінений план пошуку')
    if len(order)!=len(set(order)) or set(order)!=set(report.part_specs) or set(order)!=set(report.proofs):raise ValueError('Неповний граф доказів')
    results={}
    for id in order:
        spec=report.part_specs[id]
        from ..providers.models import RoleSettings
        RoleSettings.model_validate(spec['settings'])
        if spec['system']!=plan['system']:raise ValueError('Змінено промпт частини')
        results[id]=verify_part(attempts[report.proofs[id]],plan,spec,results,read_partial,report.story_id,report.run_id)
    validate_coverage(plan,list(report.part_specs.values()))
    if not roots or any(id not in results or report.part_specs[id]['phase']!='synthesis' for id in roots):raise ValueError('Немає фінального зведення')
    reachable=set()
    def visit(id):
        if id in reachable:return
        reachable.add(id)
        for child in report.part_specs[id]['dependencies']:visit(child)
    for id in roots:visit(id)
    if reachable!=set(order):raise ValueError('Частина не включена у фінальне зведення')
    concerns={c['id']:c for value in results.values() for c in value['concerns']}
    if not report.complete or list(concerns.values())!=[c.model_dump() for c in report.concerns]:raise ValueError('Звіт втратив зауваження')
    return results
