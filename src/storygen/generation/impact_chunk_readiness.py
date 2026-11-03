"""Frozen, costed chunk manifest preview; no network or model calls."""
from ..impact.chunking import plan_chunks
from ..impact.chunk_models import ChunkManifest
from ..impact.chunk_validation import validate_manifest
from .impact_chunk_context import build_chunk_context


def readiness(repo,request,plan=None,run=None):
    from ..billing.models import Tariff
    result=dict(ready=False,reason=None,calls=0,roles={},evaluator=None,warnings=[],protocol=2)
    try:
        m=validate_manifest(run.impact['manifest']) if run else plan_chunks(repo,plan)
        tasks=m.tasks[run.cursor:] if run else m.tasks
        if not tasks and not run:raise ValueError('Немає придатних матеріалів для перевірки частинами')
        role=m.settings;upper_bytes=[]
        for task in tasks:
            ctx=build_chunk_context(repo,m,task,{},planning=True)
            upper_bytes.append(ctx.token_estimate['body_bytes']+256)
        result.update(ready=True,plan=m.plan.model_dump(),chunk_manifest=m.model_dump(),calls=len(tasks),model=role.provider.model,provider=role.provider.provider,wire_schema_version=m.wire_schema_version,
            roles={'planner':role.provider.model_dump(include={'provider','model'})},upper_cost_nanos=None,
            part_counts={phase:sum(t['phase']==phase for t in tasks) for phase in ['delta','reduce_delta','check','reduce_check','reduce_memory']})
        result['warnings']=sorted({warning for t in m.plan.targets for warning in t.warnings})
        if role.provider.provider in {'venice','openrouter'}:
            summary=repo.billing('summary',scope='story:'+request.story_id)
            if summary['limit_nanos'] is None:raise ValueError('Спершу задайте явний ліміт бюджету оповідання')
            raw=repo.billing('tariff_get',provider=role.provider.provider,model=role.provider.model,base_url=role.provider.base_url)
            tariff=Tariff.model_validate(raw) if raw else None
            if not tariff or not tariff.current():raise ValueError('Оновіть тариф планувальника для оцінки вартості перевірки')
            result['upper_cost_nanos']=sum(tariff.price(value,role.max_output_tokens) for value in upper_bytes)
        return result
    except (ValueError,KeyError,OSError) as exc:
        result.update(ready=False,reason=str(exc) if isinstance(exc,ValueError) else 'Джерела частин недоступні')
        return result
