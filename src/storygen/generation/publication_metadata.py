"""One queued writer call for the publication source snapshot: the idea and the prose that fits (R16-SUGGEST, R-38)."""
import hashlib
import json
from importlib.resources import files
from ..authoring.blueprints import get_role_settings
from ..publication.genres import genre_catalog
from ..publication_suggestions import eligible_fields,source_stamp,fingerprint,proposal_content
from ..providers.requests import generation_request
from ..token_budget.service import token_estimate
from .context import ContextBundle,ContextOverflow


def catalog_for(language):
    # The model request names genres in the story language (#32).
    return dict(genre_catalog('en' if language=='en' else 'uk'))


SELECTION_CHANGED='Відбір сцен змінився; перегляньте його знову'


def largest_prefix(total,chars_fit,tokens_fit):
    """R16-SUGGEST-S07: the longest prefix 1..k (k<total) that fits both limits, or 0.

    The character count only grows with k, so k_chars is found by bisection; the token estimate may jump between a
    profile and the conservative byte formula, so tokens are checked downwards from k_chars (cross-review #1)."""
    low,high=0,total-1
    while low<high:
        middle=(low+high+1)//2
        if chars_fit(middle):low=middle
        else:high=middle-1
    for k in range(low,0,-1):
        if tokens_fit(k):return k
    return 0


def selection_key(selection,idea):
    return fingerprint({'included':selection['included'],'total':selection['total'],'last_scene_id':selection['last_scene_id'],
                        'idea_sha256':hashlib.sha256(idea.encode('utf-8')).hexdigest() if idea else None})


def selection_warning(selection):
    """The same content as the UI line, for MCP previews (R16-SUGGEST-S07)."""
    if not selection or selection['included']>=selection['total']:return None
    span=f"сцени 1–{selection['included']} із {selection['total']} (до «{selection['last_scene_title']}»)"
    text=(f'Книжка не вміщається у вікно моделі повністю: модель прочитає ідею твору й {span}.' if selection['idea']
          else f'Книжка не вміщається у вікно моделі повністю: модель прочитає {span}, без ідеї твору.')
    if selection.get('bound_by')=='chars':text+=' Межа — ліміт символів письменника; його можна підняти в налаштуваннях моделей.'
    return text


def build_publication_context(repo,story_id,expected_selection=None,enforce_selection=False):
    captured=repo.publication_snapshot(story_id)
    # BUILD-EDITION-001: the proposal is model-written text about every selected scene.
    from ..rating.guard import enforce_edition_limit
    enforce_edition_limit(captured.story)
    for scene,_ in captured.scenes:enforce_edition_limit(captured.story,scene)
    eligible=eligible_fields(captured.publication)
    if not eligible:raise ValueError('Немає порожніх полів, які може запропонувати модель')
    stamp=source_stamp(captured)
    # R-38: the writer gets the long-prose model and window; a cheap planner may not fit the whole book.
    writer=get_role_settings(repo,story_id).get('writer')
    if not writer or not writer.provider.model.strip():raise ValueError('Налаштуйте модель письменника')
    from ..language import load_prompt
    system=load_prompt('publication_metadata_v2',captured.story.language)
    sections=[{'title':scene.title,'text':repo.files.read(ref.relative_path,ref.sha256).decode('utf-8')} for scene,ref in captured.scenes]
    catalog=catalog_for(captured.story.language) if 'genres' in eligible else {}
    total=len(sections);limit=writer.context_tokens-writer.max_output_tokens
    built={};estimates={}
    def request(k):
        # R16-SUGGEST-S07: the idea (plan preamble) and whole scenes 1..k, never a cut scene.
        if k not in built:
            payload={'title':captured.story.title}
            if captured.idea:payload['idea']=captured.idea
            payload.update({'eligible_fields':eligible,'genre_catalog':catalog,
                            'coverage':{'scenes_included':k,'scenes_total':total},'scenes':sections[:k]})
            user=json.dumps(payload,ensure_ascii=False)
            body=generation_request('publication_suggest',writer,system,user,{})
            built[k]=(user,body,len(json.dumps(body,ensure_ascii=False,separators=(',',':'))))
        return built[k]
    def prediction(k):
        if k not in estimates:estimates[k]=token_estimate(repo,writer.provider.provider,writer.provider.base_url,request(k)[1])
        return estimates[k]
    def chars_fit(k):return request(k)[2]<=writer.max_input_chars
    def tokens_fit(k):return prediction(k)['input_tokens']<=limit
    bound_by=None
    if chars_fit(total) and tokens_fit(total):k=total
    else:
        k=largest_prefix(total,chars_fit,tokens_fit)
        if k==0:
            raise ContextOverflow(prediction(1)['input_tokens'],limit,request(1)[2],max_input_chars=writer.max_input_chars)
        over_chars=not chars_fit(k+1);over_tokens=not tokens_fit(k+1)
        bound_by='both' if over_chars and over_tokens else 'chars' if over_chars else 'tokens'
    user,body,chars=request(k);estimate=prediction(k)
    last=captured.scenes[k-1][0]
    selection={'included':k,'total':total,'last_scene_id':last.id,'last_scene_title':last.title,
               'idea':bool(captured.idea),'bound_by':bound_by}
    selection['key']=selection_key(selection,captured.idea)
    if enforce_selection and k<total and expected_selection!=selection['key']:
        # R16-SUGGEST-S07: an incomplete reading runs only as the author saw it in the preview.
        raise ValueError(SELECTION_CHANGED)
    refs=[ref.id for scene,ref in captured.scenes[:k]]
    if captured.idea_version_id:refs.append(captured.idea_version_id)
    return ContextBundle(story_id=story_id,scene_id=None,stage='publication_suggest',scene_revision=None,
        story_revision=captured.story.revision,settings=writer,system_text=system,user_text=user,
        input_refs=refs,fingerprint=fingerprint({'request':body,'sources':stamp,'prompt_version':3}),
        estimated_tokens=estimate['input_tokens'],estimate_method=estimate['method'],api_request=body,token_estimate=estimate,
        fragments={'publication_sources':json.dumps(stamp,ensure_ascii=False),
                   'publication_eligible':json.dumps(eligible),'publication_prompt_version':'3',
                   'publication_selection':json.dumps(selection,ensure_ascii=False)})


def readiness(repo,request,enforce_selection=True):
    """enforce_selection=False is the preview the author reads; enqueue and resume compare the expected selection."""
    result={'ready':False,'reason':None,'roles':{},'calls':0,'evaluator':None,'warnings':[]}
    try:
        context=build_publication_context(repo,request.story_id,request.expected_selection,enforce_selection)
        result['selection']=json.loads(context.fragments['publication_selection'])
        warning=selection_warning(result['selection'])
        if warning:result['warnings'].append(warning)
        result['roles']={'writer':context.settings.provider.model_dump(include={'provider','model'})}
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
            'failure':attempt.context.get('publication_failure'),'warnings':attempt.context.get('publication_warnings',[]),'usage':attempt.usage,'created_at':attempt.created_at,
            'selection':attempt.context.get('publication_selection')})
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
            'model':attempt.context['settings']['provider']['model'],'warnings':attempt.context.get('publication_warnings',[]),'created_at':attempt.created_at,
            'selection':attempt.context.get('publication_selection')})
    active=[{'id':run.id,'state':run.state,'error':run.error} for run in repo.list_runs(story_id)
            if run.request.mode=='publication_suggest' and run.state not in {'completed','failed','cancelled'}]
    return {'proposals':proposals,'history':history,'active_runs':active}
