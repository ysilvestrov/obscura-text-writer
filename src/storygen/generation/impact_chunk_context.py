"""Build exactly the request used for planning, budgeting and transmission."""
import json
from ..impact.models import fingerprint
from ..impact.chunking import task_payload
from ..token_budget.service import token_estimate
from .context import ContextBundle,ContextOverflow


from ..impact.chunk_requests import request_for


def measure_payload(repo,manifest,payload,*,verify_counter_files=False):
    system,user,body=request_for(manifest,payload);role=manifest.settings
    if manifest.local_token_counter is None:
        estimate=token_estimate(repo,role.provider.provider,role.provider.base_url,body)
    else:
        from ..token_budget.local_profiles import load_counter
        from ..token_budget.local_counter import predict_body,CounterUnavailable
        from ..token_budget.core import measure,estimate as conservative,endpoint_identity
        item=measure(role.provider.provider,role.provider.base_url,body)
        estimate={**conservative(item),**{k:item[k] for k in ['request_hash','body_bytes','identity']}}
        try:
            # One verified handle per immutable planning operation. Actual dispatch
            # always reloads active metadata and hashes BOTH artifact byte streams.
            if verify_counter_files or manifest._counter_runtime is None:
                try:manifest._counter_runtime=load_counter(repo.root,manifest.local_token_counter,verify_bytes=True)
                except CounterUnavailable as exc:
                    manifest._counter_runtime=str(exc)
                    raise
            counter=manifest._counter_runtime
            if isinstance(counter,str):raise CounterUnavailable(counter)
            if role.provider.provider!='local' or counter[0]['endpoint']!=endpoint_identity(role.provider.base_url):raise CounterUnavailable('local_counter_endpoint_mismatch')
            estimate.update(predict_body(body,counter))
        except (CounterUnavailable,ValueError,KeyError,TypeError,OSError) as exc:
            estimate['reasons']=[str(exc) if isinstance(exc,CounterUnavailable) else 'local_counter_unavailable']
    chars=len(json.dumps(body,ensure_ascii=False,separators=(',',':')))
    return system,user,body,estimate,chars


def fits_payload(repo,manifest,payload,fraction=1):
    required=payload.get('required_coverage',[])
    minimal=dict(covered_ids=required,summary='Перевірено.',verdict='no_impact',findings=[],evidence=[],uncertainty=None)
    if manifest.wire_schema_version==2:minimal['target_quotes']=[]
    from ..impact.result_budget import budget_size
    if budget_size(minimal,manifest.wire_schema_version)+min(512,manifest.result_cap//3)>manifest.result_cap:return False
    _,_,_,estimate,chars=measure_payload(repo,manifest,payload)
    return estimate['input_tokens']<=(manifest.settings.context_tokens-manifest.settings.max_output_tokens)*fraction and chars<=manifest.settings.max_input_chars*fraction


def build_chunk_context(repo,manifest,task,results,planning=False):
    from ..authoring.blueprints import get_role_settings
    if get_role_settings(repo,manifest.plan.story_id)['planner']!=manifest.settings:raise ValueError('Налаштування планувальника змінилися; потрібен новий перегляд частин')
    system,user,body,prediction,chars=measure_payload(repo,manifest,task_payload(manifest,task,results,planning),verify_counter_files=not planning)
    role=manifest.settings;limit=role.context_tokens-role.max_output_tokens
    if prediction['input_tokens']>limit or chars>role.max_input_chars:raise ContextOverflow(prediction['input_tokens'],limit,chars,max_input_chars=role.max_input_chars)
    target=next(t for t in manifest.plan.targets if t.version_id==task['version_id'])
    return ContextBundle(story_id=target.story_id,scene_id=target.scene_id,stage='impact_part',scene_revision=None,story_revision=repo.get_story(target.story_id).revision,settings=role,
        system_text=system,user_text=user,input_refs=list(target.source_hashes),fingerprint=fingerprint({'manifest':manifest.fingerprint,'task':task['id'],'body':body}),
        estimated_tokens=prediction['input_tokens'],estimate_method=prediction['method'],api_request=body,token_estimate=prediction,
        fragments={'impact_chunk_manifest':manifest.fingerprint,'impact_chunk_task':json.dumps(task,ensure_ascii=False),'impact_result_cap':str(manifest.result_cap)})
