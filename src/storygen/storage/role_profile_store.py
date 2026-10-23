"""Versioned templates and atomic story configuration publication."""
import json

from ..domain import RevisionConflict, new_id, now
from ..providers.models import RoleSettings
from .settings_store import write_roles_in_transaction


def _read(db,key):
    row=db.execute('SELECT payload FROM app_settings WHERE key=?',(key,)).fetchone()
    if row is None:raise KeyError(key)
    return json.loads(row[0])


def _put(db,key,payload):
    db.execute('INSERT OR REPLACE INTO app_settings VALUES(?,?)',(key,json.dumps(payload,ensure_ascii=False)))


def write_application_record(db,story_id,record):
    _put(db,'role_profile_applied:'+story_id,record)


def operation(repo,action,**data):
    from ..role_profiles import ProfileDocument
    with repo.db.connection() as db:
        if action=='list':
            rows=db.execute("SELECT payload FROM app_settings WHERE key LIKE 'role_profile:%' ORDER BY key")
            items=[json.loads(row[0]) for row in rows]
            return sorted([{'id':x['id'],'version':x['version'],'name':x['document']['name'],'created_at':x['created_at'],
                            'has_evaluator':x['document'].get('evaluator') is not None} for x in items],key=lambda x:(x['name'].casefold(),x['id'],-x['version']))
        if action=='read':return _read(db,f"role_profile:{data['profile_id']}:{data['version']}")
        db.execute('BEGIN IMMEDIATE')
        if action=='save':
            doc=ProfileDocument.model_validate(data['document'])
            if data.get('source_story_id'):
                story=repo._active_story(db,data['source_story_id'])
                if story.revision!=data['source_revision']:raise RevisionConflict('Налаштування твору вже змінено')
            id=data.get('profile_id')
            if id:
                head=_read(db,'role_profile_head:'+id)
                if head['version']!=data.get('expected_version'):raise RevisionConflict('Профіль уже має новішу версію')
                version=head['version']+1
            else:
                if data.get('expected_version') is not None:raise ValueError('Ревізію вказують лише для наявного профілю')
                id=new_id();version=1
            item={'id':id,'version':version,'document':doc.model_dump(),'created_at':now()}
            _put(db,f'role_profile:{id}:{version}',item)
            _put(db,'role_profile_head:'+id,{'version':version})
            return item
        if action=='apply':
            story=repo._active_story(db,data['story_id'])
            if story.revision!=data['expected_revision']:raise RevisionConflict('Налаштування твору вже змінено')
            _read(db,f"role_profile:{data['profile_id']}:{data['version']}")
            roles={key:RoleSettings.model_validate(value) for key,value in data['roles'].items()}
            if set(roles)!={'planner','writer','editor','memory'}:raise ValueError('Потрібні чотири ролі')
            write_roles_in_transaction(repo,db,story.id,roles)
            if data['evaluator'] is not None:
                from ..evaluation.story_adapter import EvaluationSettings,validate_evaluation_settings
                evaluator=validate_evaluation_settings(repo,EvaluationSettings.model_validate(data['evaluator']))
                _put(db,'evaluation:'+story.id,evaluator.model_dump())
            write_application_record(db,story.id,{'profile_id':data['profile_id'],'version':data['version'],'applied_at':now()})
            story.config_revision+=1
            repo._save_story(db,story)
            return repo._touch_story(db,story.id)
        raise ValueError('Невідома операція профілю')
