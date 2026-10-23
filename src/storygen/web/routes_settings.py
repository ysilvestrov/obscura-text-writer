from fastapi import APIRouter, Request

from ..authoring.blueprints import apply_blueprint, get_role_settings, save_role_settings, update_story_profile, save_shared_provider
from ..domain import DomainModel
from ..generation.models import StoryBlueprint, StyleProfile
from ..generation.prompts import default_prompt, role_prompt, expected_contract
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
    confirm_prompt_contract: bool = False
    confirm_prepare_prompt_contract: bool = False


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
    contracts={role:repo.get_version(config.prompt_version_id).prompt_contract if config.prompt_version_id else expected_contract({'planner':'brief','writer':'draft','editor':'edit','memory':'memory'}[role],config) for role,config in roles.items()}
    prepare_contract=repo.get_version(planner.prepare_prompt_version_id).prompt_contract if planner and planner.prepare_prompt_version_id else expected_contract('prepare',planner) if planner else None
    return {'story':story,'roles':roles,'profile':profile,'prompts':prompts,'prepare_prompt':preparation,'prompt_contracts':contracts,'prepare_prompt_contract':prepare_contract}


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
    stage={'planner':'brief','writer':'draft','editor':'edit','memory':'memory'}[change.role]
    if change.confirm_prompt_contract and change.prompt_text is None and settings.prompt_version_id:
        ref=repo.get_version(settings.prompt_version_id)
        if ref.story_id!=story_id or ref.kind!='prompt':raise ValueError('Чужий промпт')
        change=change.model_copy(update={'prompt_text':repo.read_text(ref.id)})
    if change.prompt_text is not None:
        standard=role_prompt({'planner':'brief','writer':'draft','editor':'edit','memory':'memory'}.get(change.role,'brief'),settings)
        if not change.prompt_text.strip() or change.prompt_text==standard:
            settings=settings.model_copy(update={'prompt_version_id':None})
        else:
            ref=repo.save_version(story_id,None,'prompt',change.prompt_text,[],prompt_contract=expected_contract(stage,settings))
            settings=settings.model_copy(update={'prompt_version_id':ref.id})
    if change.confirm_prepare_prompt_contract and change.prepare_prompt_text is None and settings.prepare_prompt_version_id:
        ref=repo.get_version(settings.prepare_prompt_version_id)
        if ref.story_id!=story_id or ref.kind!='prompt':raise ValueError('Чужий промпт')
        change=change.model_copy(update={'prepare_prompt_text':repo.read_text(ref.id)})
    if change.prepare_prompt_text is not None:
        if change.role!='planner':raise ValueError('Промпт підготовки належить планувальнику')
        id=None
        if change.prepare_prompt_text.strip() and change.prepare_prompt_text!=default_prompt('prepare'):
            id=repo.save_version(story_id,None,'prompt',change.prepare_prompt_text,[],prompt_contract=expected_contract('prepare',settings)).id
        settings=settings.model_copy(update={'prepare_prompt_version_id':id})
    return settings


@router.post('/api/providers/discover')
def models(settings: ProviderSettings):
    return {'models':discover_models(settings)}


@router.post('/api/stories/{story_id}/blueprint/apply')
def apply(story_id: str,body: BlueprintApply,request: Request):
    return apply_blueprint(request.app.state.repo,story_id,body.proposal,body.expected_revision)
