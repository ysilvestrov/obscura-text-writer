from fastapi import APIRouter, Request

from ..authoring.blueprints import apply_blueprint, get_role_settings, save_role_settings, update_story_profile, save_shared_provider
from ..domain import DomainModel
from ..generation.models import StoryBlueprint, StyleProfile
from ..generation.prompts import default_prompt, role_prompt
from ..providers.discovery import discover_models
from ..providers.models import ProviderSettings, RoleSettings

router=APIRouter()


class SettingsChange(DomainModel):
    expected_revision: int
    role: str | None = None
    settings: RoleSettings | None = None
    profile: StyleProfile | None = None
    prompt_text: str | None = None
    prepare_prompt_text: str | None = None


class BlueprintApply(DomainModel):
    expected_revision: int
    proposal: StoryBlueprint


class SharedProviderChange(SettingsChange):
    provider: ProviderSettings


@router.put('/api/stories/{story_id}/settings/shared-provider')
def shared_provider(story_id: str,change: SharedProviderChange,request: Request):
    repo=request.app.state.repo
    settings=change.settings
    if change.profile is not None:raise ValueError('Профіль зберігається окремо')
    if change.role:
        if settings is None:raise ValueError('Потрібні налаштування ролі')
        settings=configure_prompts(repo,story_id,change,settings)
    elif settings is not None or change.prompt_text is not None or change.prepare_prompt_text is not None:
        raise ValueError('Оберіть роль для налаштувань промпту')
    return save_shared_provider(repo,story_id,change.provider,change.expected_revision,change.role,settings)


@router.get('/stories/{story_id}/settings')
def page(story_id: str,request: Request):
    story=request.app.state.repo.get_story(story_id)
    return request.app.state.templates.TemplateResponse(request=request,name='settings.html',context={'story':story})


@router.get('/api/stories/{story_id}/settings')
def read_settings(story_id: str,request: Request):
    repo=request.app.state.repo
    story=repo.get_story(story_id)
    roles=get_role_settings(repo,story_id)
    prompts={role: repo.read_text(config.prompt_version_id) if config.prompt_version_id else role_prompt({'planner':'brief','writer':'draft','editor':'edit','memory':'memory'}[role],config) for role,config in roles.items()}
    profile=StyleProfile.model_validate_json(repo.read_text(story.style_version_id)) if story.style_version_id else StyleProfile()
    planner=roles.get('planner')
    preparation=repo.read_text(planner.prepare_prompt_version_id) if planner and planner.prepare_prompt_version_id else default_prompt('prepare')
    return {'story':story,'roles':roles,'profile':profile,'prompts':prompts,'prepare_prompt':preparation}


@router.put('/api/stories/{story_id}/settings')
def write_settings(story_id: str,change: SettingsChange,request: Request):
    repo=request.app.state.repo
    if change.profile is not None and change.role is None:
        return update_story_profile(repo,story_id,change.profile,change.expected_revision)
    if not change.role or change.settings is None or change.profile is not None:
        raise ValueError('Збережіть окремо профіль або одну роль')
    settings=configure_prompts(repo,story_id,change,change.settings)
    return save_role_settings(repo,story_id,change.role,settings,change.expected_revision)


def configure_prompts(repo,story_id,change,settings):
    if change.role not in {'planner','writer','editor','memory'}:raise ValueError('Невідома роль')
    if change.prompt_text is not None:
        standard=role_prompt({'planner':'brief','writer':'draft','editor':'edit','memory':'memory'}.get(change.role,'brief'),settings)
        if not change.prompt_text.strip() or change.prompt_text==standard:
            settings=settings.model_copy(update={'prompt_version_id':None})
        else:
            ref=repo.save_version(story_id,None,'prompt',change.prompt_text,[])
            settings=settings.model_copy(update={'prompt_version_id':ref.id})
    if change.prepare_prompt_text is not None:
        if change.role!='planner':raise ValueError('Промпт підготовки належить планувальнику')
        id=None
        if change.prepare_prompt_text.strip() and change.prepare_prompt_text!=default_prompt('prepare'):
            id=repo.save_version(story_id,None,'prompt',change.prepare_prompt_text,[]).id
        settings=settings.model_copy(update={'prepare_prompt_version_id':id})
    return settings


@router.post('/api/providers/discover')
def models(settings: ProviderSettings):
    return {'models':discover_models(settings)}


@router.post('/api/stories/{story_id}/blueprint/apply')
def apply(story_id: str,body: BlueprintApply,request: Request):
    return apply_blueprint(request.app.state.repo,story_id,body.proposal,body.expected_revision)
