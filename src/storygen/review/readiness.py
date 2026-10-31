"""Read-only scene-session preview; future call counts remain explicitly unknown."""
from ..authoring.blueprints import get_role_settings
from .capture import plan_review,modes_for
from ..impact.models import fingerprint
from .planning import prepare_scene,check_specs


def readiness(repo,request,run=None):
    result=dict(ready=False,reason=None,protocol=3,calls=0,roles={},evaluator=None,warnings=[],upper_cost_nanos=None)
    try:
        view=repo.context_view(request.story_id);scenes=view.list_scenes(request.story_id)
        roles=get_role_settings(repo,request.story_id)
        if not all(name in roles for name in ['planner','memory']):raise ValueError('Налаштуйте планувальника й роль пам’яті')
        result['roles']={name:roles[name].provider.model_dump(include={'provider','model'}) for name in ['planner','memory']}
        plan=plan_review(view)
        result['basis_modes']=modes_for(view,plan.targets)
        if not run and not plan.targets:raise ValueError('Немає матеріалів, які потребують перевірки')
        if run and [s.id for s in scenes]!=run.impact['scene_order']:raise ValueError('Порядок сцен змінився; створіть нову перевірку')
        result.update(plan=plan.model_dump(),fingerprint=fingerprint([[(s.id,s.heads) for s in scenes],plan.fingerprint,{k:roles[k].model_dump() for k in ['planner','memory']}]),
            model=roles['planner'].provider.model,provider=roles['planner'].provider.provider,scene_count=len(scenes),future_calls_unknown=True)
        if plan.targets and not run:
            first=prepare_scene(repo,plan.targets[0].scene_id)
            result['calls']=len(first['delta_specs'])+len(check_specs(repo,first,{}))+1
        for name in ['planner','memory']:
            role=roles[name]
            if role.provider.provider in {'venice','openrouter'}:
                from ..billing.models import Tariff
                if repo.billing('summary',scope='story:'+request.story_id)['limit_nanos'] is None:raise ValueError('Спершу задайте явний ліміт бюджету оповідання')
                raw=repo.billing('tariff_get',provider=role.provider.provider,model=role.provider.model,base_url=role.provider.base_url)
                if not raw or not Tariff.model_validate(raw).current():raise ValueError('Оновіть тариф ролі '+name)
                # The live next-scene plan cannot have an honest all-book price yet.
                result['paid']=True
                if run and request.budget_limit_usd is None:raise ValueError('Потрібен явний ліміт бюджету перевірки')
        result['warnings']=['Кількість викликів наведено лише для початкового пошуку. Наступні сцени та оновлення пам’яті плануються послідовно; бюджет перевіряється перед кожним платним викликом.']
        if 'current_consistency' in result['basis_modes'].values():result['warnings'].append('Частина старих матеріалів не має історичної бази. Їх перевірятимемо за поточними передумовами без порівняння «було → стало».')
        result['ready']=True
    except (ValueError,KeyError,OSError) as exc:result.update(ready=False,reason=str(exc))
    return result
