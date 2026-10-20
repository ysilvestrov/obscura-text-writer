from ..generation.models import StoryBlueprint
from .context import build_context, make_context
from .stages import execute_stage

STAGES=('brief','draft','edit','memory')
STAGE_ROLES={'prepare':'planner','brief':'planner','draft':'writer','edit':'editor','memory':'memory'}


def generate_scene(repo,scene_id: str,role_settings: dict,gateway_factory,cancel,on_event,run_id=None) -> list:
    attempts=[]
    for stage in STAGES:
        if cancel.is_set():
            break
        role=role_settings[STAGE_ROLES[stage]]
        context=build_context(repo,scene_id,stage,role)
        on_event('stage_started',{'stage':stage,'scene_id':scene_id})
        attempt=execute_stage(repo,scene_id,stage,context,gateway_factory(role.provider),cancel,lambda text:on_event('delta',{'stage':stage,'text':text}),run_id)
        attempts.append(attempt)
        on_event('stage_finished',{'attempt_id':attempt.id,'state':attempt.state})
        if attempt.state!='completed':
            break
    return attempts


def prepare_story(repo,story_id: str,planner,gateway,cancel,run_id=None) -> StoryBlueprint:
    story=repo.get_story(story_id)
    sources=[s for s in [repo.active_source(story_id,'source_plan'),repo.active_source(story_id,'source_characters')] if s]
    sections=[f'АВТОРСЬКЕ ДЖЕРЕЛО [version_id={v.id}]\n'+repo.read_text(v.id) for v in sources]
    context=make_context(repo,story,None,'prepare',planner,sections,[v.id for v in sources])
    attempt=execute_stage(repo,None,'prepare',context,gateway,cancel,lambda text:None,run_id)
    if attempt.state!='completed':
        raise ValueError('Не вдалося підготувати пропозицію структури; сирий результат збережено')
    return StoryBlueprint.model_validate_json(repo.read_text(attempt.result_version_id))
