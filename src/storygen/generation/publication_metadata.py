"""One queued planner call for the complete publication source snapshot."""
import json
from importlib.resources import files
from ..authoring.blueprints import get_role_settings
from ..publication.genres import genre_catalog
from ..publication_suggestions import eligible_fields,source_stamp,fingerprint,proposal_content
from ..providers.requests import generation_request
from ..token_budget.service import token_estimate
from .context import ContextBundle,ContextOverflow


def build_publication_context(repo,story_id):
    captured=repo.publication_snapshot(story_id)
    eligible=eligible_fields(captured.publication)
    if not eligible:raise ValueError('Немає порожніх полів, які може запропонувати модель')
    stamp=source_stamp(captured)
    planner=get_role_settings(repo,story_id).get('planner')
    if not planner or not planner.provider.model.strip():raise ValueError('Налаштуйте модель планувальника')
    system=files('storygen.generation').joinpath('resources/publication_metadata_uk_v1.txt').read_text(encoding='utf-8')
    sections=[{'title':scene.title,'text':repo.files.read(ref.relative_path,ref.sha256).decode('utf-8')} for scene,ref in captured.scenes]
    user=json.dumps({'title':captured.story.title,'eligible_fields':eligible,
        'genre_catalog':dict(genre_catalog()) if 'genres' in eligible else {},'scenes':sections},ensure_ascii=False)
    body=generation_request('publication_suggest',planner,system,user,{})
    prediction=token_estimate(repo,planner.provider.provider,planner.provider.base_url,body)
    chars=len(json.dumps(body,ensure_ascii=False,separators=(',',':')))
    limit=planner.context_tokens-planner.max_output_tokens
    if prediction['input_tokens']>limit or chars>planner.max_input_chars:
        error=ContextOverflow(prediction['input_tokens'],limit,chars)
        if chars>planner.max_input_chars:
            error.args=(str(error)+f' Ліміт запиту: {planner.max_input_chars} символів.',)
        raise error
    return ContextBundle(story_id=story_id,scene_id=None,stage='publication_suggest',scene_revision=None,
        story_revision=captured.story.revision,settings=planner,system_text=system,user_text=user,
        input_refs=[ref.id for scene,ref in captured.scenes],fingerprint=fingerprint({'request':body,'sources':stamp,'prompt_version':2}),
        estimated_tokens=prediction['input_tokens'],estimate_method=prediction['method'],api_request=body,token_estimate=prediction,
        fragments={'publication_sources':json.dumps(stamp,ensure_ascii=False),
                   'publication_eligible':json.dumps(eligible),'publication_prompt_version':'2'})


def readiness(repo,request):
    result={'ready':False,'reason':None,'roles':{},'calls':0,'evaluator':None,'warnings':[]}
    try:
        context=build_publication_context(repo,request.story_id)
        result['roles']={'planner':context.settings.provider.model_dump(include={'provider','model'})}
        if context.settings.provider.provider in {'venice','openrouter'} and repo.billing('summary',scope='story:'+request.story_id)['limit_nanos'] is None:
            raise ValueError('Спершу задайте явний ліміт бюджету оповідання')
        result.update(ready=True,calls=1,eligible_fields=json.loads(context.fragments['publication_eligible']),
            estimated_tokens=context.estimated_tokens,input_budget=context.settings.context_tokens-context.settings.max_output_tokens)
    except (ValueError,KeyError) as exc:
        result['reason']=str(exc) if isinstance(exc,ValueError) else 'Матеріал не знайдено'
    return result


def suggestions_state(repo,story_id):
    snapshot=repo.publication_snapshot(story_id)
    try:stamp=source_stamp(snapshot);reason=None
    except ValueError as exc:stamp=None;reason=str(exc)
    proposals=[];history=[]
    for attempt in reversed(repo.list_attempts(story_id)):
        if attempt.stage!='publication_suggest':continue
        history.append({'attempt_id':attempt.id,'run_id':attempt.run_id,'state':attempt.state,'error':attempt.error,
            'failure':attempt.context.get('publication_failure'),'warnings':attempt.context.get('publication_warnings',[]),'usage':attempt.usage,'created_at':attempt.created_at})
        proposal=attempt.context.get('publication_proposal')
        if attempt.state!='completed' or not proposal:continue
        run_ready=not attempt.run_id or repo.get_run(attempt.run_id).state=='completed'
        current=stamp==proposal.get('source_stamp') and run_ready
        available=[key for key in proposal['suggestions'] if key in eligible_fields(snapshot.publication)]
        valid_hash=proposal.get('fingerprint')==fingerprint(proposal_content(proposal))
        proposals.append({'attempt_id':attempt.id,'run_id':attempt.run_id,'fingerprint':proposal['fingerprint'],
            'suggestions':proposal['suggestions'],'available_fields':available,
            'can_apply':current and valid_hash and bool(available),
            'reason':None if current and valid_hash and available else reason or 'Пропозиція застаріла, поля вже заповнені або запуск не завершено',
            'model':attempt.context['settings']['provider']['model'],'warnings':attempt.context.get('publication_warnings',[]),'created_at':attempt.created_at})
    active=[{'id':run.id,'state':run.state,'error':run.error} for run in repo.list_runs(story_id)
            if run.request.mode=='publication_suggest' and run.state not in {'completed','failed','cancelled'}]
    return {'proposals':proposals,'history':history,'active_runs':active}
