"""Read-only run preflight shared by the queue and workspace controls."""

from ..authoring.blueprints import get_role_settings
from .context import build_context, make_context
from .pipeline import STAGES, STAGE_ROLES


def preview(repo, request):
    story=repo.get_story(request.story_id)
    scenes=repo.list_scenes(story.id)
    scene=next((s for s in scenes if s.id==request.scene_id),None)
    stages=[request.stage] if request.mode=='stage' else ['prepare'] if request.mode=='prepare' else ['memory'] if request.mode=='rebuild_memory' else list(STAGES)
    settings=get_role_settings(repo,story.id)
    roles={name:settings[name].provider.model_dump(include={'provider','model'}) for stage in stages if (name:=STAGE_ROLES[stage]) in settings}
    result={'ready':False,'reason':None,'roles':roles,'calls':len(stages),'evaluator':None,'warnings':[]}
    try:
        if request.mode!='prepare' and scene is None:
            raise ValueError('Оберіть сцену')
        targets=[s for s in scenes if s.position>=scene.position] if request.mode in {'remaining','rebuild_memory'} else [scene]
        result['calls']=len(stages)*len(targets)
        for stage in stages:
            name=STAGE_ROLES[stage]
            if name not in settings or not settings[name].provider.model.strip():
                raise ValueError('Роль не налаштовано: '+name)
            role=settings[name]
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
                from ..evaluation.blocks import get_block, blocked_message
                block = get_block(repo, story.id, evaluation.config)
                if block and evaluation.policy == 'pause_on_failure':
                    raise ValueError(blocked_message(block))
                if block:
                    result['warning'] = blocked_message(block)
                else:
                    result['evaluator']=evaluation.config.model_dump(include={'provider','model'})
                    result['calls']+=len(targets)
        if request.mode=='prepare':
            view=repo.context_view(story.id)
            story=view.get_story(story.id)
            sources=[s for s in [view.active_source(story.id,'source_plan'),view.active_source(story.id,'source_characters')] if s]
            if not sources or not any(repo.read_text(s.id).strip() for s in sources):
                raise ValueError('Спершу імпортуйте авторський план або описи персонажів')
            if any(s.stale or not s.complete for s in sources):
                raise ValueError('Авторські джерела потребують оновлення')
            make_context(view,story,None,'prepare',settings['planner'],[view.read_text(s.id) for s in sources],[s.id for s in sources])
        else:
            if stages[0]=='brief':
                for target in targets:
                    plan_id=target.heads.get('plan')
                    plan=repo.read_text(plan_id) if plan_id else target.beats
                    if not plan.strip():
                        raise ValueError(f'Спершу додайте план сцени {target.position+1}')
            if request.mode=='rebuild_memory':
                for target in targets:
                    prose=repo.get_version(target.heads['prose']) if target.heads.get('prose') else None
                    if not prose or not prose.complete or prose.kind not in {'edited','manual'}:
                        raise ValueError(f'Спершу виберіть завершену прозу сцени {target.position+1}')
            # Later tasks may consume outputs that this run has not generated yet.
            context=build_context(repo,scene.id,stages[0],settings[STAGE_ROLES[stages[0]]])
            result['warnings']=context.context_warnings.copy()
            literary=any(stage in {'brief','draft'} or stage=='edit' and settings['editor'].edit_mode=='prose' for stage in stages)
            if literary:
                from ..characters.context import character_material
                view=repo.context_view(story.id)
                for target in targets:
                    _,warnings,_=character_material(view,view.get_story(story.id),view.get_scene(target.id))
                    result['warnings'].extend(warnings)
                result['warnings']=list(dict.fromkeys(result['warnings']))
        result['ready']=True
    except (ValueError,KeyError) as exc:
        result['reason']=str(exc) if isinstance(exc,ValueError) else 'Матеріал не знайдено; оновіть сторінку'
    return result


def pending_preview(repo,run):
    tasks=run.tasks[run.cursor:]
    result={'ready':False,'reason':None,'roles':{},'calls':0,'evaluator':None}
    try:
        if not tasks:raise ValueError('Усі етапи запуску завершено')
        first=tasks[0]
        if first['stage']!='evaluate':
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
                prompt_id=role.prepare_prompt_version_id if task['stage']=='prepare' else role.prompt_version_id
                if prompt_id:
                    prompt=repo.get_version(prompt_id)
                    if prompt.story_id!=run.story_id or prompt.kind!='prompt' or prompt.stale or not prompt.complete:raise ValueError('Промпт ролі потребує оновлення: '+name)
                result['roles'][name]=role.provider.model_dump(include={'provider','model'})
            result['calls']+=1
        result['ready']=True
    except (ValueError,KeyError) as exc:
        result.update(ready=False,reason=str(exc) if isinstance(exc,ValueError) else 'Матеріал не знайдено; оновіть сторінку')
    return result
