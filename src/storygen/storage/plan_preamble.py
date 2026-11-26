"""PLAN-PREAMBLE: the author edits the plan preamble (global author notes) after import.

The preamble stays part of the active `source_plan`; a change is a new plan version with the same scene sections,
prepared like an import (the version is saved first) and published in one transaction."""
from ..domain import RevisionConflict, Scene
from ..plan_sections import PreambleError, preamble_editable, preamble_text, replace_preamble, split_plan


def _lf(text):
    return text.replace('\r\n','\n')


def read_plan_preamble(repo,story_id):
    ref=repo.active_source(story_id,'source_plan')
    if not ref:
        return {'text':'','plan_version_id':None,'editable':False,'reason':'no_plan'}
    text=repo.read_text(ref.id)
    editable=preamble_editable(text)
    return {'text':preamble_text(text),'plan_version_id':ref.id,'editable':editable,'reason':None if editable else 'no_scenes'}


def _series_lines(repo,story_id,text):
    from ..book import guard
    if not guard.story_long_prose(repo,story_id):return False
    from ..plan_sections import cut_series_lines
    kept,lines,unusable=cut_series_lines(text)
    return lines is not None or unusable


def replace_plan_preamble(repo,story_id,expected_plan_version_id,text):
    previous=repo.active_source(story_id,'source_plan')
    if not previous:raise ValueError('У творі ще немає плану. Імпортуйте план із заголовками сцен.')
    if previous.id!=expected_plan_version_id:raise RevisionConflict('План твору вже змінено; перечитайте вступ')
    raw=repo.read_text(previous.id)
    old=split_plan(raw)[0]
    if _lf(old).strip()==_lf(text).strip():
        return {'changed':False,'plan_version_id':previous.id,'revision':repo.get_story(story_id).revision}
    if _series_lines(repo,story_id,text):raise ValueError('Серію змінюють у налаштуваннях твору, розділ «Серія», а не у вступі плану.')
    candidate,_=replace_preamble(raw,text)
    version=repo.save_version(story_id,None,'source_plan',candidate,[previous.id])
    from .invalidation import invalidate_in_transaction
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        current=repo._active_source(db,story_id,'source_plan')
        if not current or current.id!=previous.id:raise RevisionConflict('План твору вже змінено; перечитайте вступ')
        db.execute('INSERT INTO active_sources VALUES(?,?,?) ON CONFLICT(story_id,kind) DO UPDATE SET version_id=excluded.version_id',
                   (story_id,'source_plan',version.id))
        # The same preservation as an additive import: author scene plans, canon and cards are not made stale.
        authored={Scene.model_validate_json(r[0]).heads.get('plan') for r in db.execute('SELECT payload FROM scenes WHERE story_id=?',(story_id,))}
        invalidate_in_transaction(repo,db,[previous.id],exclude={version.id},preserve=authored|{story.canon_version_id,story.characters_version_id})
        story=repo._touch_story(db,story_id)
    return {'changed':True,'plan_version_id':version.id,'revision':story.revision}


__all__=['PreambleError','read_plan_preamble','replace_plan_preamble']
