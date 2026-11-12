"""Read-only run preflight shared by the queue and workspace controls."""

import re

from ..authoring.blueprints import get_role_settings
from ..memory.journal import load_memory
from .context import build_context, make_context
from .pipeline import STAGES, STAGE_ROLES
from .prompts import validate_role_prompt
from .role_routing import WRITER_STAGES, settings_for, uses_low_rating_variant
from ..providers.policy import STAGE_POLICY_ROLE, check_consent, check_refusal, request_rating


_SLOT_EVENT=re.compile(r'"slot"\s*:\s*"')


def _check_model_policy(repo,role,provider,rating):
    """MODEL-003/MODEL-004 offline: the same refusal and consent check `execute_stage` makes, before the run starts."""
    check_refusal(repo,role,provider,rating)
    if provider.provider!='venice':  # Venice consent depends on its live catalog; the gateway checks it.
        check_consent(repo,role,provider,rating,None)


def unconfirmed_core_scenes(view, scenes) -> int:
    """Active scenes whose memory head has a core (a slot event) the author has not confirmed (MEMORY-CONFIRM).

    Counted once per captured view; a head is parsed only when its raw text can contain a set slot."""
    cached=getattr(view,'_unconfirmed_core_scenes',None)
    if cached is not None:return cached
    count=0
    for scene in scenes:
        memory_id=scene.heads.get('memory')
        if not memory_id:continue
        try:
            if view.peek_version(memory_id).memory_confirmation is not None:continue
            raw=view.read_text(memory_id)
            if not _SLOT_EVENT.search(raw):continue
            journal=load_memory(raw)
        except (ValueError,KeyError,OSError):continue
        if any(event.slot for event in journal.events):count+=1
    view._unconfirmed_core_scenes=count
    return count


def preview(repo, request, view=None):
    if request.mode=='impact':
        from .impact_context import readiness
        return readiness(repo,request)
    if request.mode=='rewrite':
        from .assisted_writing import readiness
        return readiness(repo,request)
    if request.mode=='publication_suggest':
        from .publication_metadata import readiness
        return readiness(repo,request)
    if request.mode=='edit_loop':
        from .editor_loop import readiness
        return readiness(repo,request,view=view)
    if request.mode=='classify':
        from .edit_classification import readiness
        return readiness(repo,request)
    story=repo.get_story(request.story_id)
    # One captured view serves the whole check; preview never reads needs_review.
    # A caller-supplied view (all operations of one request) replaces the per-operation capture.
    if view is None and request.mode!='prepare':view=repo.context_view(story.id)
    scenes=view.list_scenes(story.id) if view is not None else repo.list_scenes(story.id)
    scene=next((s for s in scenes if s.id==request.scene_id),None)
    stages=[request.stage] if request.mode=='stage' else ['prepare'] if request.mode=='prepare' else ['memory'] if request.mode=='rebuild_memory' else list(STAGES)
    settings=get_role_settings(repo,story.id)
    roles={name:settings[name].provider.model_dump(include={'provider','model'}) for stage in stages if (name:=STAGE_ROLES[stage]) in settings}
    result={'ready':False,'reason':None,'roles':roles,'calls':len(stages),'evaluator':None,'warnings':[]}
    # Information only: auto mode never waits for confirmation, so the count changes neither ready nor reason.
    if request.mode in {'scene','remaining'}:result['unconfirmed_core_scenes']=unconfirmed_core_scenes(view,scenes)
    try:
        if request.mode!='prepare' and scene is None:
            raise ValueError('Оберіть сцену')
        targets=[s for s in scenes if s.position>=scene.position] if request.mode in {'remaining','rebuild_memory'} else [scene]
        result['calls']=len(stages)*len(targets)
        if request.mode in {'scene','remaining'} and request.edit_workflow=='loop':
            result.update(edit_loop_scenes=len(targets),edit_pass_limit=request.edit_pass_limit)
            result['calls']+=(request.edit_pass_limit-1)*len(targets)
        for stage in stages:
            name=STAGE_ROLES[stage]
            if name not in settings or not settings[name].provider.model.strip():
                raise ValueError('Роль не налаштовано: '+name)
            role=settings[name]
            if name=='writer' and role.low_rating_variant is not None and stage in WRITER_STAGES and not role.low_rating_variant.provider.model.strip():
                raise ValueError('Не задано модель письменника для сцен 0–1')
            validate_role_prompt(repo,story.id,stage,role)
            prompt_id=role.prepare_prompt_version_id if stage=='prepare' else role.prompt_version_id
            if prompt_id:
                prompt=repo.get_version(prompt_id)
                if prompt.story_id!=story.id or prompt.kind!='prompt' or prompt.stale or not prompt.complete:
                    raise ValueError('Промпт ролі потребує оновлення: '+name)
        if request.mode in {'scene','remaining'}:
            from ..evaluation.story_adapter import get_evaluation_settings
            try:
                evaluation=get_evaluation_settings(repo,story.id)
            except ValueError:
                evaluation=None
            if evaluation and evaluation.policy!='off':
                from ..evaluation.story_adapter import evaluated_scenes
                evaluated=[t for t in targets if evaluated_scenes(repo,story,scenes,t.id)]
            if evaluation and evaluation.policy!='off' and evaluated:
                from ..evaluation.blocks import get_block, blocked_message
                block = get_block(repo, story.id, evaluation.config)
                if block and evaluation.policy == 'pause_on_failure':
                    raise ValueError(blocked_message(block))
                if block:
                    result['warning'] = blocked_message(block)
                else:
                    result['evaluator']=evaluation.config.model_dump(include={'provider','model'})
                    result['calls']+=len(evaluated)
        if request.mode=='prepare':
            if view is None:view=repo.context_view(story.id)
            story=view.get_story(story.id)
            from .prepare_sources import prepare_sources
            sources=prepare_sources(view,story)
            if not sources or not any(repo.read_text(s.id).strip() for s in sources):
                raise ValueError('Спершу імпортуйте авторський план або описи персонажів')
            if any(s.stale or not s.complete for s in sources):
                raise ValueError('Авторські джерела потребують оновлення')
            make_context(view,story,None,'prepare',settings['planner'],[view.read_text(s.id) for s in sources],[s.id for s in sources])
            _check_model_policy(repo,'planner',settings['planner'].provider,request_rating(view,story,[]))
        else:
            if stages[0]=='brief':
                for target in targets:
                    plan_id=target.heads.get('plan')
                    plan=view.read_text(plan_id) if plan_id else target.beats
                    if not plan.strip():
                        raise ValueError(f'Спершу додайте план сцени {target.position+1}')
            if request.mode=='rebuild_memory':
                for target in targets:
                    prose=view.peek_version(target.heads['prose']) if target.heads.get('prose') else None
                    if not prose or not prose.complete or prose.kind not in {'edited','manual'}:
                        raise ValueError(f'Спершу виберіть завершену прозу сцени {target.position+1}')
            # Every target scene passes the rating guard before the run starts, not only the first.
            from ..rating.guard import enforce_rating
            rated_story=view.get_story(story.id)
            writer=settings.get('writer')
            if writer is not None and any(stage in WRITER_STAGES for stage in stages) and any(uses_low_rating_variant(writer,rated_story,view.get_scene(t.id)) for t in targets):
                result['roles']['writer_low_rating']=writer.low_rating_variant.provider.model_dump(include={'provider','model'})
            for target in targets:
                for stage in stages:
                    enforce_rating(view,rated_story,target,stage)
                    policy_role=STAGE_POLICY_ROLE[stage]
                    _check_model_policy(repo,policy_role,settings_for(settings[policy_role],policy_role,rated_story,view.get_scene(target.id)).provider,request_rating(view,rated_story,[target.id]))
            # Later tasks may consume outputs that this run has not generated yet.
            from ..memory.reuse import MemoryApprovalRequired
            try:
                context=build_context(repo,scene.id,stages[0],settings[STAGE_ROLES[stages[0]]],memory_approval=request.memory_approval,view=view)
            except MemoryApprovalRequired as approval:
                if request.mode!='stage' or request.stage!='memory':raise
                # Probe all remaining limits before offering consent; never enqueue this probe.
                context=build_context(repo,scene.id,'memory',settings['memory'],memory_approval=approval.review['fingerprint'],view=view)
                result['memory_review']=approval.review
            result['warnings']=context.context_warnings.copy()
            literary=any(stage in {'brief','draft'} or stage=='edit' and settings['editor'].edit_mode=='prose' for stage in stages)
            if literary:
                from ..characters.context import character_material
                for target in targets:
                    _,warnings,_=character_material(view,view.get_story(story.id),view.get_scene(target.id))
                    result['warnings'].extend(warnings)
                result['warnings']=list(dict.fromkeys(result['warnings']))
        providers=[item.get('provider') for item in result.get('roles',{}).values()]
        if result.get('evaluator'):providers.append(result['evaluator'].get('provider'))
        if any(provider in {'venice','openrouter'} for provider in providers):
            if repo.billing('summary',scope='story:'+story.id)['limit_nanos'] is None:
                raise ValueError('Спершу задайте явний ліміт бюджету в налаштуваннях')
        result['ready']=True
        if result.get('memory_review'):
            result.update(ready=False,can_confirm=True,reason='Попередня пам’ять потребує авторського підтвердження')
    except (ValueError,KeyError) as exc:
        result['reason']=str(exc) if isinstance(exc,ValueError) else 'Матеріал не знайдено; оновіть сторінку'
    return result


def pending_preview(repo,run):
    if run.request.mode=='impact':
        from .impact_context import readiness
        return readiness(repo,run.request,run)
    if run.request.mode=='rewrite':
        if any(a.stage=='rewrite' and a.context.get('rewrite_proposal') for a in repo.list_attempts(run.story_id,run.id)):
            return dict(ready=False,reason='Спершу перегляньте пропозицію письменника; новий виклик запускається окремо',roles={},calls=0,evaluator=None)
        from .assisted_writing import readiness
        return readiness(repo,run.request)
    if run.request.mode=='publication_suggest':
        from .publication_metadata import readiness
        return readiness(repo,run.request)
    if run.request.mode=='edit_loop':
        from .editor_loop import readiness
        return readiness(repo,run.request,run)
    if run.request.mode=='classify':
        from .edit_classification import readiness
        return readiness(repo,run.request)
    tasks=run.tasks[run.cursor:]
    result={'ready':False,'reason':None,'roles':{},'calls':0,'evaluator':None}
    try:
        if not tasks:raise ValueError('Усі етапи запуску завершено')
        first=tasks[0]
        if run.state=='needs_review' and first['stage']=='edit' and any(
                a.stage=='edit' and a.scene_id==first.get('scene_id') and a.context.get('run_cursor')==run.cursor and a.context.get('copyedit_proposal')
                for a in repo.list_attempts(run.story_id,run.id)):
            raise ValueError('Спершу прийміть вибрані правки; далі використайте «Продовжити після прийнятого етапу», без повтору редактора')
        if first.get('editor_loop'):
            from .editor_loop import readiness
            result=readiness(repo,run.request,run)
            if not result['ready']:return result
        elif first['stage']!='evaluate':
            request=run.request.model_copy(update={'mode':'prepare' if first['stage']=='prepare' else 'stage','stage':None if first['stage']=='prepare' else first['stage'],'scene_id':first.get('scene_id')})
            result=preview(repo,request)
            if not result['ready']:return result
        settings=get_role_settings(repo,run.story_id)
        result.update(roles={},calls=0,evaluator=None)
        for task in tasks:
            if task['stage']=='evaluate':
                from ..evaluation.story_adapter import get_evaluation_settings, build_evaluation_case
                evaluation=get_evaluation_settings(repo,run.story_id)
                if evaluation.policy=='off':continue
                from ..evaluation.blocks import get_block, blocked_message
                block = get_block(repo, run.story_id, evaluation.config)
                if block:
                    if evaluation.policy == 'pause_on_failure' or run.request.mode == 'evaluate':
                        raise ValueError(blocked_message(block))
                    result['warning'] = blocked_message(block)
                    continue
                if task is first:build_evaluation_case(repo,run.story_id,task.get('scene_id'),task.get('evaluation_mode',run.request.evaluation_mode))
                result['evaluator']=evaluation.config.model_dump(include={'provider','model'})
            else:
                name=STAGE_ROLES[task['stage']]
                if name not in settings or not settings[name].provider.model.strip():raise ValueError('Роль не налаштовано: '+name)
                role=settings[name]
                validate_role_prompt(repo,run.story_id,task['stage'],role)
                prompt_id=role.prepare_prompt_version_id if task['stage']=='prepare' else role.prompt_version_id
                if prompt_id:
                    prompt=repo.get_version(prompt_id)
                    if prompt.story_id!=run.story_id or prompt.kind!='prompt' or prompt.stale or not prompt.complete:raise ValueError('Промпт ролі потребує оновлення: '+name)
                result['roles'][name]=role.provider.model_dump(include={'provider','model'})
            if task.get('editor_loop'):
                from .editor_loop import model_attempts
                result['calls']+=max(0,run.request.edit_pass_limit-len(model_attempts(repo,run))) if task is first else run.request.edit_pass_limit
            else:result['calls']+=1
        providers=[role.get('provider') for role in result['roles'].values()]
        if result.get('evaluator'):providers.append(result['evaluator'].get('provider'))
        if any(p in {'venice','openrouter'} for p in providers) and repo.billing('summary',scope='story:'+run.story_id)['limit_nanos'] is None:
            raise ValueError('Спершу задайте явний ліміт бюджету в налаштуваннях')
        result['ready']=True
    except (ValueError,KeyError) as exc:
        result.update(ready=False,reason=str(exc) if isinstance(exc,ValueError) else 'Матеріал не знайдено; оновіть сторінку')
    return result
