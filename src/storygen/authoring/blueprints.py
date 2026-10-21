import json

from ..domain import RevisionConflict, Story
from ..generation.models import StoryBlueprint, StyleProfile
from ..providers.models import RoleSettings

ROLES={'planner','writer','editor','memory'}


def save_shared_provider(repo,story_id,provider,expected_revision,current_role=None,current_settings=None):
    if current_role is not None and (current_role not in ROLES or current_settings is None):
        raise ValueError('Невідома роль для спільного збереження')
    rows=get_role_settings(repo,story_id)
    if current_role:rows[current_role]=current_settings
    updates={role:rows.get(role,RoleSettings(provider=provider)).model_copy(update={'provider':provider}).model_dump() for role in sorted(ROLES)}
    return repo.write_role_settings(story_id,updates,expected_revision)


def parse_blueprint(raw: str) -> StoryBlueprint:
    return StoryBlueprint.model_validate_json(raw)


def get_role_settings(repo,story_id: str) -> dict[str,RoleSettings]:
    return {role:RoleSettings.model_validate({'memory_mode':'snapshot',**raw}) for role,raw in repo.read_role_settings(story_id).items()}


def save_role_settings(repo,story_id: str,role: str,settings: RoleSettings,expected_revision: int) -> Story:
    return repo.write_role_settings(story_id,{role:settings.model_dump()},expected_revision)


def update_story_profile(repo,story_id: str,profile: StyleProfile,expected_revision: int) -> Story:
    version=repo.save_version(story_id,None,'style',profile.model_dump_json(),[])
    return repo.publish_story_material(story_id,'style_version_id',version.id,expected_revision)


def apply_blueprint(repo,story_id: str,proposal: StoryBlueprint,expected_revision: int) -> Story:
    story=repo.get_story(story_id)
    if story.revision!=expected_revision:
        raise RevisionConflict('Матеріали вже змінено')
    source_ids=[]
    for card in proposal.characters:
        for source in card.sources:
            ref=repo.get_version(source.version_id)
            if ref.story_id!=story_id or ref.kind not in {'source_plan','source_characters'} or source.quote not in repo.read_text(ref.id):
                raise ValueError('Картка персонажа не має підтвердженого джерела')
            source_ids.append(ref.id)
    canon=repo.save_version(story_id,None,'canon',proposal.canon,source_ids)
    characters=repo.save_version(story_id,None,'character_cards',json.dumps([c.model_dump() for c in proposal.characters],ensure_ascii=False),source_ids)
    # Existing scenes remain under author control; proposals never overwrite their plans.
    existing=repo.list_scenes(story_id)
    planned=[] if existing else [(scene,repo.save_version(story_id,None,'scene_plan',scene.beats,[])) for scene in proposal.scenes]
    return repo.publish_blueprint(story_id,canon.id,characters.id,planned,expected_revision)
