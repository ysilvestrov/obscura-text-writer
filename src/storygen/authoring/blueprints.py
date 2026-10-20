import json

from ..domain import RevisionConflict, Story, Scene, SceneCreate, new_id
from ..generation.models import StoryBlueprint, StyleProfile
from ..providers.models import RoleSettings

ROLES={'planner','writer','editor','memory'}


def save_shared_provider(repo,story_id,provider,expected_revision,current_role=None,current_settings=None):
    if current_role is not None and (current_role not in ROLES or current_settings is None):
        raise ValueError('Невідома роль для спільного збереження')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:
            raise RevisionConflict('Налаштування вже змінено')
        rows={row[0]:RoleSettings.model_validate_json(row[1]) for row in db.execute('SELECT role,payload FROM role_settings WHERE story_id=?',(story_id,))}
        if current_role:rows[current_role]=current_settings
        for role in sorted(ROLES):
            settings=rows.get(role,RoleSettings(provider=provider)).model_copy(update={'provider':provider})
            for id in [settings.prompt_version_id,settings.prepare_prompt_version_id]:
                if id:
                    ref=repo.get_version(id)
                    if ref.story_id!=story_id or ref.kind!='prompt':raise ValueError('Промпт належить іншому твору')
            db.execute('INSERT OR REPLACE INTO role_settings VALUES(?,?,?)',(story_id,role,settings.model_dump_json()))
        return repo._touch_story(db,story_id)


def parse_blueprint(raw: str) -> StoryBlueprint:
    return StoryBlueprint.model_validate_json(raw)


def get_role_settings(repo,story_id: str) -> dict[str,RoleSettings]:
    repo.get_story(story_id)
    with repo.db.connection() as db:
        return {row[0]:RoleSettings.model_validate_json(row[1]) for row in db.execute('SELECT role,payload FROM role_settings WHERE story_id=?',(story_id,))}


def save_role_settings(repo,story_id: str,role: str,settings: RoleSettings,expected_revision: int) -> Story:
    if role not in ROLES:
        raise ValueError('Невідома роль')
    for id in [settings.prompt_version_id,settings.prepare_prompt_version_id]:
        if not id:continue
        ref=repo.get_version(id)
        if ref.story_id!=story_id or ref.kind!='prompt':
            raise ValueError('Промпт належить іншому твору або має інший тип')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:
            raise RevisionConflict('Налаштування вже змінено')
        db.execute('INSERT OR REPLACE INTO role_settings VALUES(?,?,?)',(story_id,role,settings.model_dump_json()))
        return repo._touch_story(db,story_id)


def update_story_profile(repo,story_id: str,profile: StyleProfile,expected_revision: int) -> Story:
    version=repo.save_version(story_id,None,'style',profile.model_dump_json(),[])
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:
            raise RevisionConflict('Профіль уже змінено')
        previous=story.style_version_id
        story.style_version_id=version.id
        story.revision+=1
        repo._save_story(db,story)
        if previous:
            from ..generation.dependencies import invalidate_in_transaction
            invalidate_in_transaction(repo,db,[previous])
        else:
            from ..generation.dependencies import invalidate_story_materials
            invalidate_story_materials(repo,db,story_id)
    return story


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
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        current=repo._active_story(db,story_id)
        if current.revision!=expected_revision:
            raise RevisionConflict('Матеріали вже змінено')
        current.canon_version_id=canon.id
        current.characters_version_id=characters.id
        current.revision+=1
        repo._save_story(db,current)
        from ..generation.dependencies import invalidate_in_transaction
        invalidate_in_transaction(repo,db,[id for id in [story.canon_version_id,story.characters_version_id] if id])
        from ..generation.dependencies import invalidate_story_materials
        invalidate_story_materials(repo,db,story_id)
        for position,(data,plan) in enumerate(planned):
            scene=Scene(id=new_id(),story_id=story_id,**{**data.model_dump(),'position':position})
            scene.heads['plan']=plan.id
            db.execute('INSERT INTO scenes VALUES(?,?,?,?)',(scene.id,story_id,position,scene.model_dump_json()))
            plan.scene_id=scene.id
            db.execute('UPDATE versions SET scene_id=?,payload=? WHERE id=?',(scene.id,plan.model_dump_json(),plan.id))
    return current
