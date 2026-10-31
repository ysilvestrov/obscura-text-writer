"""Isolated planner contracts; no writer context or global prompt injection."""
import json
from importlib.resources import files
from ..authoring.blueprints import get_role_settings
from ..impact.models import fingerprint,ImpactTarget
from ..providers.requests import generation_request
from ..token_budget.service import token_estimate
from .context import ContextBundle,ContextOverflow


def build_impact_context(repo,target,stage,delta=None):
    target=ImpactTarget.model_validate(target)
    if target.blockers:raise ValueError('; '.join(target.blockers))
    role=get_role_settings(repo,target.story_id).get('planner')
    if not role or not role.provider.model.strip():raise ValueError('Налаштуйте модель планувальника')
    if stage not in {'impact_delta','impact_check'}:raise ValueError('Невідомий етап перевірки впливу')
    system=files('storygen.generation').joinpath('resources/'+stage+'_uk_v1.txt').read_text(encoding='utf-8')
    data={'sources':[c.model_dump() for c in target.changes if stage=='impact_check' or c.changed]}
    if stage=='impact_check':
        data.update(target={'version_id':target.version_id,'text':target.text,'content_format':target.content_format,'scene':target.scene_title,'scene_number':target.position+1},delta=delta)
    omitted_memory=False
    include_memory=stage=='impact_check' and bool(target.memory_text)
    if include_memory:data['own_memory']={'version_id':target.memory_id,'evidence_status':target.memory_evidence_status,'journal':json.loads(target.memory_text)}
    user=json.dumps(data,ensure_ascii=False)
    body=generation_request(stage,role,system,user,{})
    prediction=token_estimate(repo,role.provider.provider,role.provider.base_url,body)
    chars=len(json.dumps(body,ensure_ascii=False,separators=(',',':')))
    limit=role.context_tokens-role.max_output_tokens
    if (prediction['input_tokens']>limit or chars>role.max_input_chars) and include_memory:
        omitted_memory=True;include_memory=False;data.pop('own_memory',None);user=json.dumps(data,ensure_ascii=False)
        body=generation_request(stage,role,system,user,{})
        prediction=token_estimate(repo,role.provider.provider,role.provider.base_url,body)
        chars=len(json.dumps(body,ensure_ascii=False,separators=(',',':')))
    if prediction['input_tokens']>limit or chars>role.max_input_chars:
        raise ContextOverflow(prediction['input_tokens'],limit,chars,max_input_chars=role.max_input_chars)
    return ContextBundle(story_id=target.story_id,scene_id=target.scene_id,stage=stage,scene_revision=None,
        story_revision=repo.get_story(target.story_id).revision,settings=role,system_text=system,user_text=user,
        input_refs=list(target.source_hashes),fingerprint=fingerprint({'target':target.fingerprint,'body':body,'protocol':1}),
        estimated_tokens=prediction['input_tokens'],estimate_method=prediction['method'],api_request=body,token_estimate=prediction,context_warnings=target.warnings+(['Журнал пам’яті не вмістився в контекст; перевіряється лише цільовий текст.'] if omitted_memory else []),
        fragments={'impact_target':target.model_dump_json(),'impact_prompt_version':'1','impact_memory_included':'true' if include_memory else 'false'})


def tasks_for(plan):
    groups={};tasks=[]
    for target in plan.targets:
        if target.blockers:continue
        groups.setdefault(target.group_id,target)
    for group,target in groups.items():tasks.append(dict(stage='impact_delta',scene_id=target.scene_id,group_id=group,version_id=target.version_id))
    for target in plan.targets:
        if not target.blockers:tasks.append(dict(stage='impact_check',scene_id=target.scene_id,group_id=target.group_id,version_id=target.version_id))
    return tasks


def readiness(repo,request,run=None):
    if request.impact_protocol==3 or run and run.impact.get('protocol')==3:
        from ..review.readiness import readiness as scene_readiness
        return scene_readiness(repo,request,run)
    from ..impact.planning import plan_impact
    from ..impact.models import ImpactPlan
    from ..billing.models import Tariff
    result=dict(ready=False,reason=None,calls=0,roles={},evaluator=None,warnings=[])
    if run and run.impact.get('protocol')==2:
        from .impact_chunk_readiness import readiness as chunk_readiness
        return chunk_readiness(repo,request,run=run)
    try:
        plan=ImpactPlan.model_validate(run.impact['plan']) if run else plan_impact(repo.context_view(request.story_id))
        result['plan']=plan.model_dump()
        result['warnings']=sorted({warning for t in plan.targets for warning in t.warnings})
        tasks=run.tasks[run.cursor:] if run else tasks_for(plan)
        if run:
            while tasks:
                task=tasks[0];target=next(t for t in plan.targets if t.version_id==task['version_id'])
                if not reusable_attempt(repo,run,task,target):break
                tasks=tasks[1:]
            if not tasks:return {**result,'ready':True,'calls':0}
        if not tasks:raise ValueError('Немає матеріалів із відтворюваними зміненими передумовами')
        targets={t.version_id:t for t in plan.targets}
        role=get_role_settings(repo,request.story_id).get('planner')
        if not role:raise ValueError('Налаштуйте модель планувальника')
        from ..impact.chunking import wire_version_for
        if not run and wire_version_for(role)==2:
            from .impact_chunk_readiness import readiness as chunk_readiness
            return chunk_readiness(repo,request,plan=plan)
        # Preflight known source and target payloads, without inventing a future delta.
        try:
            for task in tasks:build_impact_context(repo,targets[task['version_id']],task['stage'])
        except ContextOverflow:
            if run:raise
            from .impact_chunk_readiness import readiness as chunk_readiness
            return chunk_readiness(repo,request,plan=plan)
        result.update(plan=plan.model_dump(),calls=len(tasks),roles={'planner':role.provider.model_dump(include={'provider','model'})},ready=True,
            model=role.provider.model,provider=role.provider.provider,upper_cost_nanos=None)
        if role.provider.provider in {'venice','openrouter'}:
            summary=repo.billing('summary',scope='story:'+request.story_id)
            if summary['limit_nanos'] is None:raise ValueError('Спершу задайте явний ліміт бюджету оповідання')
            raw=repo.billing('tariff_get',provider=role.provider.provider,model=role.provider.model,base_url=role.provider.base_url)
            tariff=Tariff.model_validate(raw) if raw else None
            if not tariff or not tariff.current():raise ValueError('Оновіть тариф планувальника для оцінки вартості перевірки')
            result['upper_cost_nanos']=len(tasks)*tariff.price(role.max_input_chars*4+256,role.max_output_tokens)
        return result
    except (ValueError,KeyError,OSError) as exc:
        result.update(ready=False,reason=str(exc) if isinstance(exc,ValueError) else 'Джерела перевірки недоступні')
        return result


def reusable_attempt(repo,run,task,target):
    from ..impact.validation import validate_delta,validate_check,decode_response
    attempts=[a for a in repo.list_attempts(run.story_id,run.id) if a.context.get('run_cursor')==run.cursor and a.stage==task['stage']]
    completed=next((a for a in reversed(attempts) if a.state=='completed' and a.finish_reason=='stop' and a.context.get('impact_target')==target.model_dump()),None)
    if completed:
        payload=decode_response(repo.files.read_partial(completed.partial_path))
        result=(validate_delta if task['stage']=='impact_delta' else validate_check)(payload,target)
        if result.model_dump()!=completed.context.get('impact_result'):raise ValueError('Збережена відповідь перевірки впливу пошкоджена')
    return completed
