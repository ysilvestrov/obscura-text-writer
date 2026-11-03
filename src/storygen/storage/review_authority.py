"""Append-only, scene/material-scoped author decisions with a common revision gate."""
import json
from ..domain import RevisionConflict
from ..impact.models import fingerprint
from ..review.evidence import statement,validate_priorities


def _derive(policy,command):
    decisions=list(policy['decisions']);statements=dict(policy['statements'])
    remove=command.get('revoke_id') or command.get('replace_id')
    if remove:
        if not any(d['id']==remove for d in decisions):raise ValueError('Невідоме рішення для скасування або заміни')
        decisions=[d for d in decisions if d['id']!=remove]
    if command.get('revoke_id'):decision_id=remove
    else:
        preferred,superseded=command['preferred'],command['superseded']
        for value in [preferred,superseded]:
            if not isinstance(value,dict) or value.get('id')!=fingerprint({k:v for k,v in value.items() if k!='id'}):raise ValueError('Підроблена ідентичність твердження')
            statements[value['id']]=value
        decision_id=fingerprint(command)
        decisions.append(dict(id=decision_id,preferred_statement_id=preferred['id'],superseded_statement_id=superseded['id']))
    validate_priorities(decisions,statements)
    return dict(revision=policy['revision']+1,decisions=decisions,statements=statements),decision_id


def load(db,story_id):
    policies={};operations={}
    base='review-authority:'+story_id+':'
    for key,raw in db.execute('SELECT key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid',(base+'%',)):
        event=json.loads(raw);command=event['command'];scope=(command['scene_id'],command['material'])
        previous=policies.get(scope,dict(revision=0,decisions=[],statements={}))
        if (event['story_id']!=story_id or key!=base+command['operation_id'] or event['revision']!=previous['revision']+1
            or event['previous_hash']!=fingerprint(previous) or event['command_hash']!=fingerprint(command)):
            raise ValueError('Пошкоджений журнал авторських пріоритетів')
        if command['story_id']!=story_id or command['material'] not in {'brief','prose'} or command['expected_revision']!=previous['revision']:raise ValueError('Некоректна область журналу пріоритетів')
        derived,decision_id=_derive(previous,command)
        if derived!={k:event[k] for k in ['revision','decisions','statements']} or event['decision_id']!=decision_id:raise ValueError('Пріоритет не відповідає первинній авторській операції')
        policies[scope]=derived;operations[command['operation_id']]=event
    return policies,operations


def snapshot(repo,story_id,scene_id):
    with repo.db.connection() as db:
        repo._active_story(db,story_id)
        scene=repo._active_scene(db,scene_id)
        if scene.story_id!=story_id:raise ValueError('Стороння сцена')
        policies,_=load(db,story_id)
    decisions=[];statements={};revisions={}
    for material in ['brief','prose']:
        policy=policies.get((scene_id,material),dict(revision=0,decisions=[],statements={}))
        revisions[material]=policy['revision'];statements.update(policy['statements'])
        decisions.extend({**d,'material':material} for d in policy['decisions'])
    return dict(priorities=decisions,statements=statements,authority_revisions=revisions)


def _live_statements(view,scene_id,material,values):
    from ..review.capture import capture
    from ..review.planning4 import registry_for
    scene=view.get_scene(scene_id);head=scene.heads.get(material)
    if not head:raise ValueError('Немає матеріалу для авторського рішення')
    target=capture(view,head,'current_consistency')
    if target.blockers:raise ValueError('; '.join(target.blockers))
    reg=registry_for([target.model_dump()])
    for value in values:
        found=False
        for ref,row in reg.items():
            if row['kind']!='source' or row['side']!='new':continue
            if row['version_id']!=value['version_id'] or row['document_hash']!=value['document_hash']:continue
            try:
                got=statement(reg,dict(ref=ref,start=value['start']-row['start'],end=value['end']-row['start'],quote=value['quote']))
                if got==value:found=True;break
            except (ValueError,KeyError,TypeError):continue
        if not found:raise ValueError('Твердження відсутнє в чинних передумовах або змінено його доказ')


def priority_decide(repo,story_id,scene_id,material,expected_revision,operation_id,preferred=None,superseded=None,revoke_id=None,replace_id=None):
    if material not in {'brief','prose'} or not operation_id or len(operation_id)>200:raise ValueError('Некоректна область або ID рішення')
    if bool(revoke_id)==bool(preferred or superseded) or revoke_id and replace_id:raise ValueError('Оберіть створення, заміну або скасування рішення')
    command=dict(story_id=story_id,scene_id=scene_id,material=material,expected_revision=expected_revision,operation_id=operation_id,
                 preferred=preferred,superseded=superseded,revoke_id=revoke_id,replace_id=replace_id)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE');repo._active_story(db,story_id)
        scene=repo._active_scene(db,scene_id)
        if scene.story_id!=story_id:raise ValueError('Стороння сцена')
        policies,operations=load(db,story_id)
        if operation_id in operations:
            old=operations[operation_id]
            if old['command']!=command:raise ValueError('ID рішення вже використаний з іншими даними')
            return dict(revision=old['revision'],decision_id=old['decision_id'])
        policy=policies.get((scene_id,material),dict(revision=0,decisions=[],statements={}))
        if type(expected_revision) is not int or policy['revision']!=expected_revision:raise RevisionConflict('Авторські пріоритети змінилися')
        if not revoke_id:
            if preferred is None or superseded is None:raise ValueError('Потрібні два твердження')
            from .context_view import ContextView
            _live_statements(ContextView(repo,db,story_id),scene_id,material,[preferred,superseded])
        derived,decision_id=_derive(policy,command)
        event=dict(story_id=story_id,**derived,
            previous_hash=fingerprint(policy),command_hash=fingerprint(command),command=command,decision_id=decision_id)
        db.execute('INSERT INTO app_settings VALUES(?,?)',('review-authority:'+story_id+':'+operation_id,json.dumps(event,ensure_ascii=False)))
        scene.needs_review=True;scene.revision+=1;repo._save_scene(db,scene);repo._touch_story(db,story_id)
        from ..run_models import Run
        for payload, in db.execute('SELECT payload FROM runs WHERE story_id=?',(story_id,)).fetchall():
            run=Run.model_validate_json(payload)
            if run.impact and run.impact.get('protocol')==3 and run.state=='needs_review' and run.impact.get('scene_plan',{}).get('scene_id')==scene_id:
                run.state='alternative';run.error='Авторські пріоритети змінилися; створіть нову перевірку'
                db.execute('UPDATE runs SET state=?,payload=? WHERE id=?',(run.state,run.model_dump_json(),run.id))
    return dict(revision=event['revision'],decision_id=decision_id)


def revision(view,scene_id,material):
    return view.review_authority.get((scene_id,material),{}).get('revision',0)
