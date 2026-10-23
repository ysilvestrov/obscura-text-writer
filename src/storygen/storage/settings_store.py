from ..domain import RevisionConflict, VersionRef
from ..providers.models import RoleSettings

ROLES = {'planner', 'writer', 'editor', 'memory'}


def read_role_settings(repo, story_id):
    with repo.db.connection() as db:
        repo._active_story(db, story_id)
        return {row[0]: RoleSettings.model_validate({'memory_mode':'snapshot',**json.loads(row[1])}).model_dump() for row in db.execute(
            'SELECT role,payload FROM role_settings WHERE story_id=?', (story_id,))}


def write_role_settings(repo, story_id, updates, expected_revision):
    if set(updates) - ROLES:
        raise ValueError('Невідома роль')
    settings = {role: RoleSettings.model_validate(raw) for role, raw in updates.items()}
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        if story.revision != expected_revision:
            raise RevisionConflict('Налаштування вже змінено')
        write_roles_in_transaction(repo,db,story_id,settings)
        story.config_revision += 1
        repo._save_story(db, story)
        return repo._touch_story(db, story_id)


def write_roles_in_transaction(repo,db,story_id,settings):
    for role, item in settings.items():
        for id in [item.prompt_version_id, item.prepare_prompt_version_id]:
            if id:
                ref = repo._get(db, 'versions', id, VersionRef)
                if ref.story_id != story_id or ref.kind != 'prompt':
                    raise ValueError('Промпт належить іншому твору або має інший тип')
        from ..prompt_contracts import validate_role_prompt
        from .context_view import ContextView
        view=ContextView(repo,db,story_id)
        validate_role_prompt(view,story_id,{'planner':'brief','writer':'draft','editor':'edit','memory':'memory'}[role],item)
        if role=='planner':validate_role_prompt(view,story_id,'prepare',item)
        db.execute('INSERT OR REPLACE INTO role_settings VALUES(?,?,?)', (story_id, role, item.model_dump_json()))


import json


def _read(repo, key):
    with repo.db.connection() as db:
        row = db.execute('SELECT payload FROM app_settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None


def read_evaluator_settings(repo, story_id):
    return _read(repo, 'evaluation:' + story_id)


def write_evaluator_settings(repo, story_id, payload):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db, story_id)
        story.config_revision += 1
        repo._save_story(db, story)
        repo._touch_story(db, story_id)
        db.execute('INSERT OR REPLACE INTO app_settings VALUES(?,?)', ('evaluation:' + story_id, json.dumps(payload, ensure_ascii=False)))


def read_calibration(repo, id):
    return _read(repo, 'calibration:' + id)


def register_calibration(repo, id, payload):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR REPLACE INTO app_settings VALUES(?,?)', ('calibration:' + id, json.dumps(payload, ensure_ascii=False)))


def read_refusal_block(repo, story_id, identity_hash):
    return _read(repo, 'evaluator_block:' + story_id + ':' + identity_hash)


def record_refusal_block(repo, story_id, identity_hash, payload):
    if payload.get('story_id') != story_id or not payload.get('failure', {}).get('category', '').startswith('refusal_'):
        raise ValueError('Лише відмова оцінювача створює блокування')
    key = 'evaluator_block:' + story_id + ':' + identity_hash
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR IGNORE INTO app_settings VALUES(?,?)', (key, json.dumps(payload, ensure_ascii=False)))
        return json.loads(db.execute('SELECT payload FROM app_settings WHERE key=?', (key,)).fetchone()[0])
