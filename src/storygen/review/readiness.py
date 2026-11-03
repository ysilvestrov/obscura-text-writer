"""Read-only scene-session preview; future call counts remain explicitly unknown."""
from ..authoring.blueprints import get_role_settings
from .capture import plan_review,modes_for
from ..impact.models import fingerprint
from .planning import prepare_scene,check_specs


def readiness(repo,request,run=None):
    result=dict(ready=False,reason=None,protocol=3,calls=0,roles={},evaluator=None,warnings=[],upper_cost_nanos=None)
    try:
        view=repo.context_view(request.story_id);scenes=view.list_scenes(request.story_id)
        version=request.review_contract_version or 3
        result['contract_version']=version
        authority=[[s.id,m,view.review_authority.get((s.id,m),{}).get('revision',0)] for s in scenes for m in ['brief','prose']]
        if version==3 and any(row[2] for row in authority):raise ValueError('Для авторських пріоритетів потрібна перевірка нового формату')
        roles=get_role_settings(repo,request.story_id)
        if not all(name in roles for name in ['planner','memory']):raise ValueError('Налаштуйте планувальника й роль пам’яті')
        result['roles']={name:roles[name].provider.model_dump(include={'provider','model'}) for name in ['planner','memory']}
        plan=plan_review(view)
        result['basis_modes']=modes_for(view,plan.targets)
        if not run and not plan.targets:raise ValueError('Немає матеріалів, які потребують перевірки')
        if run and [s.id for s in scenes]!=run.impact['scene_order']:raise ValueError('Порядок сцен змінився; створіть нову перевірку')
        result.update(plan=plan.model_dump(),fingerprint=fingerprint([[(s.id,s.heads) for s in scenes],plan.fingerprint,{k:roles[k].model_dump() for k in ['planner','memory']}]),
            model=roles['planner'].provider.model,provider=roles['planner'].provider.provider,scene_count=len(scenes),future_calls_unknown=True)
        if version==4:result['fingerprint']=fingerprint([result['fingerprint'],version,authority])
        if plan.targets and not run:
            first=prepare_scene(repo,plan.targets[0].scene_id,contract_version=version)
            result['calls']=len(first['delta_specs'])+len(check_specs(repo,first,{}))+1
            if version==4:
                if first['settings']['provider']['provider']=='local':
                    from ..token_budget.local_profiles import load_counter
                    if not first['local_token_counter']:raise ValueError('Активуйте кваліфікований локальний лічильник для нового промпту перевірки')
                    try:load_counter(repo.root,first['local_token_counter'],verify_bytes=True)
                    except (ValueError,OSError) as exc:raise ValueError('Кваліфікований локальний лічильник недоступний; відновіть його перед запуском') from exc
                from .planning import premise_specs
                from .planning4 import initial_counts
                result['part_counts']=initial_counts(repo,first)
                result['calls']=sum(result['part_counts'].values())
                result['calls_upper_bound']=10000
                result['automatic_acceptance_allowed']=False
        if version==4 and run and run.impact.get('phase')=='search':
            saved=run.impact['scene_plan']
            if saved['settings']['provider']['provider']=='local':
                from ..token_budget.local_profiles import load_counter
                if not saved.get('local_token_counter'):raise ValueError('Активуйте кваліфікований локальний лічильник для нового промпту перевірки')
                try:load_counter(repo.root,saved['local_token_counter'],verify_bytes=True)
                except (ValueError,OSError) as exc:raise ValueError('Кваліфікований локальний лічильник недоступний; відновіть його перед запуском') from exc
        for name in ['planner','memory']:
            role=roles[name]
            if role.provider.provider in {'venice','openrouter'}:
                from ..billing.models import Tariff
                if repo.billing('summary',scope='story:'+request.story_id)['limit_nanos'] is None:raise ValueError('Спершу задайте явний ліміт бюджету оповідання')
                raw=repo.billing('tariff_get',provider=role.provider.provider,model=role.provider.model,base_url=role.provider.base_url)
                if not raw or not Tariff.model_validate(raw).current():raise ValueError('Оновіть тариф ролі '+name)
                # The live next-scene plan cannot have an honest all-book price yet.
                result['paid']=True
                if version==4 and name=='planner':
                    tariff=Tariff.model_validate(raw)
                    result['initial_search_upper_cost_nanos']=10000*tariff.price(role.max_input_chars*4+256,role.max_output_tokens)
                if run and request.budget_limit_usd is None:raise ValueError('Потрібен явний ліміт бюджету перевірки')
        result['warnings']=['Кількість викликів наведено лише для початкового пошуку. Наступні сцени та оновлення пам’яті плануються послідовно; бюджет перевіряється перед кожним платним викликом.']
        if version==4:result['warnings'].append('Початковий підрахунок може зрости після отримання доказів; межа пошуку однієї сцени — 10000 частин. Верхня оцінка вартості охоплює цю межу, не весь твір і не оновлення пам’яті. Незавершені результати не приймаються.')
        if 'current_consistency' in result['basis_modes'].values():result['warnings'].append('Частина старих матеріалів не має історичної бази. Їх перевірятимемо за поточними передумовами без порівняння «було → стало».')
        result['ready']=True
    except (ValueError,KeyError,OSError) as exc:result.update(ready=False,reason=str(exc))
    return result
