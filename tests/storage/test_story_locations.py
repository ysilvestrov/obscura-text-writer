"""MEMORY-LOCATIONS-S02/S03: saving a plan creates location cards and Scene.location_ids; migration 007 backfills."""
import json
import sqlite3

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.locations import location_id, normalize
from storygen.storage import locations as store
from storygen.storage.database import SCHEMA_VERSION
from storygen.storage.repository import Repository



def lid(story,*parts):
    return location_id(story.id,normalize(parts))


def make(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    return repo,story,repo.create_scene(story.id,SceneCreate(title='Сцена'))


def cards(repo,story):
    with repo.db.connection() as db:return store.load_locations(db,story.id)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_plan_save_creates_cards_with_parents_and_scene_location_ids(tmp_path):
    repo,story,scene=make(tmp_path)
    saved=repo.update_scene_plan(scene.id,'Сцена 1: Ранок\nЛокація: Дім / кухня, потім двір.\nДії: сніданок.',scene.revision)
    assert saved.location_ids==[lid(story,'Дім','кухня'),lid(story,'двір')]
    found=cards(repo,story)
    assert set(found)=={lid(story,'Дім'),lid(story,'Дім','кухня'),lid(story,'двір')}
    assert found[lid(story,'Дім','кухня')].parent_id==lid(story,'Дім')
    assert found[lid(story,'Дім','кухня')].path=='Дім / кухня'
    assert found[lid(story,'двір')].parent_id is None and found[lid(story,'двір')].description==''


@pytest.mark.req('MEMORY-LOCATIONS')
def test_the_first_spelling_stays_the_shown_path(tmp_path):
    repo,story,scene=make(tmp_path)
    saved=repo.update_scene_plan(scene.id,'Локація: Маєток Джорджа',scene.revision)
    again=repo.update_scene_plan(scene.id,'Локація: маєток  джорджа.',saved.revision)
    assert again.location_ids==saved.location_ids
    assert cards(repo,story)[saved.location_ids[0]].path=='Маєток Джорджа'


@pytest.mark.req('MEMORY-LOCATIONS')
def test_a_plan_without_a_location_line_has_no_locations(tmp_path):
    repo,story,scene=make(tmp_path)
    saved=repo.update_scene_plan(scene.id,'Локація: Дім',scene.revision)
    cleared=repo.update_scene_plan(scene.id,'Дії: тиша.',saved.revision)
    assert cleared.location_ids==[]
    assert lid(story,'Дім') in cards(repo,story)  # cards stay for the merge panel


@pytest.mark.req('MEMORY-LOCATIONS')
def test_scene_created_with_a_plan_gets_locations(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена',beats='Локація: Ліс'))
    assert repo.get_scene(scene.id).location_ids==[lid(story,'Ліс')]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_a_changed_location_line_stales_legacy_versions_like_a_changed_cast(tmp_path):
    repo,story,scene=make(tmp_path)
    saved=repo.update_scene_plan(scene.id,'Локація: Дім',scene.revision)
    brief=repo.save_version(story.id,scene.id,'brief','завдання',[])
    with repo.db.connection() as db:
        row=json.loads(db.execute('SELECT payload FROM scenes WHERE id=?',(scene.id,)).fetchone()[0])
        row['heads']['brief']=brief.id
        db.execute('UPDATE scenes SET payload=? WHERE id=?',(json.dumps(row,ensure_ascii=False),scene.id))
    repo.db.bump_generation()
    current=repo.get_scene(scene.id)
    repo.update_scene_plan(scene.id,'Локація: Ліс',current.revision)
    # VALID-LINKS: a brief the author wrote is never stale (owner, 23.11.2026).
    assert not repo.get_version(brief.id).stale


@pytest.mark.req('MEMORY-LOCATIONS')
def test_merge_split_description_and_dismissed_pairs(tmp_path):
    repo,story,scene=make(tmp_path)
    repo.update_scene_plan(scene.id,'Локація: Квартира Джорджа, Квартира Джоржа',scene.revision)
    a,b=lid(story,'Квартира Джорджа'),lid(story,'Квартира Джоржа')
    with repo.db.connection() as db:
        store.merge_location(db,story.id,b,a)
        assert store.load_locations(db,story.id)[b].merged_into==a
        with pytest.raises(ValueError):store.merge_location(db,story.id,a,b)  # no cycles
        with pytest.raises(ValueError):store.merge_location(db,story.id,a,a)
        store.split_location(db,story.id,b)
        assert store.load_locations(db,story.id)[b].merged_into is None
        store.set_description(db,story.id,a,'  Тісна кухня з вікном у двір.  ')
        assert store.load_locations(db,story.id)[a].description=='Тісна кухня з вікном у двір.'
        with pytest.raises(ValueError):store.set_description(db,story.id,a,'х'*2001)
        assert store.suggestions(db,story.id)==[(a,b)]
        store.dismiss_pair(db,story.id,b,a)
        assert store.suggestions(db,story.id)==[]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_migration_from_6_backfills_every_scene_without_new_revisions(tmp_path):
    repo,story,scene=make(tmp_path)
    trashed=repo.create_scene(story.id,SceneCreate(title='У кошику'))
    path=repo.root/'storygen.sqlite3'
    with sqlite3.connect(path) as db:
        for item,beats,extra in [(scene,'Локація: Дім / кухня',{}),(trashed,'Локація: Ліс',{'trashed_at':'2026-11-01T00:00:00+00:00'})]:
            row=json.loads(db.execute('SELECT payload FROM scenes WHERE id=?',(item.id,)).fetchone()[0])
            row.pop('location_ids',None);row.update(beats=beats,**extra)
            db.execute('UPDATE scenes SET payload=? WHERE id=?',(json.dumps(row,ensure_ascii=False),item.id))
        db.execute('DROP TABLE location_dismissals');db.execute('DROP TABLE story_locations')
        db.execute('PRAGMA user_version=6')
    before={s.id:s.revision for s in [scene,trashed]}
    again=Repository(repo.root)
    with again.db.connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==SCHEMA_VERSION==7
        rows={r[0]:json.loads(r[1]) for r in db.execute('SELECT id,payload FROM scenes')}
        assert rows[scene.id]['location_ids']==[lid(story,'Дім','кухня')]
        assert rows[trashed.id]['location_ids']==[lid(story,'Ліс')]
        assert {k:v['revision'] for k,v in rows.items()}==before
        assert set(store.load_locations(db,story.id))=={lid(story,'Дім'),lid(story,'Дім','кухня'),lid(story,'Ліс')}


@pytest.mark.req('MEMORY-LOCATIONS')
def test_integrity_flags_a_scene_with_a_missing_location_card(tmp_path):
    from storygen.storage.integrity import check_integrity
    repo,story,scene=make(tmp_path)
    repo.update_scene_plan(scene.id,'Локація: Дім',scene.revision)
    assert check_integrity(repo.root).ok
    with repo.db.connection() as db:db.execute('DELETE FROM story_locations')
    assert any(i.code=='location_unknown' for i in check_integrity(repo.root).issues)


def set_model_places(repo,scene_id,ids):
    """Places as an accepted proposal leaves them (CHARACTER-EXTRACT): source `model`."""
    with repo.db.connection() as db:
        row=json.loads(db.execute('SELECT payload FROM scenes WHERE id=?',(scene_id,)).fetchone()[0])
        row.update(location_ids=ids,location_source='model')
        db.execute('UPDATE scenes SET payload=? WHERE id=?',(json.dumps(row,ensure_ascii=False),scene_id))
    repo.db.bump_generation()
    return repo.get_scene(scene_id)


@pytest.mark.req('MEMORY-LOCATIONS')
@pytest.mark.parametrize('source',['plan','model'])
@pytest.mark.parametrize('line',[None,'','Ліс'])
def test_plan_rule_keeps_model_places(tmp_path,source,line):
    repo,story,scene=make(tmp_path)
    with repo.db.connection() as db:store.ensure_locations(db,story.id,[('Дім',)])
    before=[lid(story,'Дім')]
    scene=set_model_places(repo,scene.id,before) if source=='model' else repo.update_scene_plan(scene.id,'Локація: Дім',scene.revision)
    assert scene.location_source==source
    plan='Дії: тиша.' if line is None else f'Локація: {line}\nДії: тиша.'
    saved=repo.update_scene_plan(scene.id,plan,scene.revision)
    if line:  # a non-empty plan line always wins
        assert (saved.location_ids,saved.location_source)==([lid(story,'Ліс')],'plan')
    elif source=='model':
        assert (saved.location_ids,saved.location_source)==(before,'model')
    else:
        assert (saved.location_ids,saved.location_source)==([],'plan')


@pytest.mark.req('MEMORY-LOCATIONS')
def test_cards_sync_keeps_model_places(tmp_path):
    from storygen.storage.scene_metadata import sync_story_cast
    repo,story,scene=make(tmp_path)
    with repo.db.connection() as db:store.ensure_locations(db,story.id,[('Дім',)])
    set_model_places(repo,scene.id,[lid(story,'Дім')])
    with repo.write_transaction() as db:sync_story_cast(repo,db,story.id)
    assert repo.get_scene(scene.id).location_ids==[lid(story,'Дім')]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_an_old_scene_reads_as_plan_source(tmp_path):
    repo,story,scene=make(tmp_path)
    with repo.db.connection() as db:
        row=json.loads(db.execute('SELECT payload FROM scenes WHERE id=?',(scene.id,)).fetchone()[0])
        row.pop('location_source',None)
        db.execute('UPDATE scenes SET payload=? WHERE id=?',(json.dumps(row,ensure_ascii=False),scene.id))
    repo.db.bump_generation()
    assert repo.get_scene(scene.id).location_source=='plan'


@pytest.mark.req('MEMORY-LOCATIONS')
def test_plan_source_stays_out_of_the_payload(tmp_path):
    # An older build forbids unknown scene fields: only a scene with model places carries the new field.
    repo,story,scene=make(tmp_path)
    with repo.db.connection() as db:
        row=json.loads(db.execute('SELECT payload FROM scenes WHERE id=?',(scene.id,)).fetchone()[0])
    assert 'location_source' not in row
    with repo.db.connection() as db:store.ensure_locations(db,story.id,[('Дім',)])
    set_model_places(repo,scene.id,[lid(story,'Дім')])
    saved=repo.update_scene_plan(scene.id,'Дії: тиша.',repo.get_scene(scene.id).revision)
    assert json.loads(saved.model_dump_json())['location_source']=='model'
