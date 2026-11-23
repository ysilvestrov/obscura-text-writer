"""R-44 PR 1: R-28 (impact check, review3/4, review authority) is removed; its stored records are inert history."""
import json
import sqlite3

import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.dependencies import save_manual_prose
from storygen.storage.backup import create_backup
from storygen.storage.integrity import check_integrity
from storygen.storage.repository import Repository
from storygen.storage.snapshots import resolve_freshness


def stale_book(tmp_path):
    repo=Repository(tmp_path/'data')
    story=repo.create_story(StoryCreate(title='Історія'))
    for n in range(2):
        scene=repo.create_scene(story.id,SceneCreate(title=f'Сцена {n+1}',beats=f'План {n+1}'))
        save_manual_prose(repo,scene.id,f'Проза {n+1}.',scene.revision)
    accepted=repo.preview_prose_acceptance(story.id)
    repo.accept_all_prose(story.id,accepted['fingerprint'])
    ids=[s.id for s in repo.list_scenes(story.id)]
    repo.reorder_scenes(story.id,[ids[1],ids[0]],repo.get_story(story.id).revision)
    return repo,story


def old_records(repo,story,version_id,scene_id):
    """Rows an R-28 database holds; their payloads are not valid for any current model."""
    rows={f'impact:{story.id}:report:r1':{'id':'r1','story_id':story.id,'target':{'version_id':version_id},'verdict':'no_impact'},
          f'impact:{story.id}:application:a1':{'id':'a1','story_id':story.id,'report_id':'r1'},
          f'review3:{story.id}:acceptance:x1':{'target':{'version_id':version_id,'baseline_ids':{}}},
          f'review4:{story.id}:acceptance:x2':{'target':{'version_id':version_id,'baseline_ids':{}}},
          f'review-authority:{story.id}:op1':{'story_id':story.id,'revision':1,'command':{'scene_id':scene_id,'material':'prose','operation_id':'op1'}}}
    with sqlite3.connect(repo.root/'storygen.sqlite3') as db:
        db.executemany('INSERT INTO app_settings(key,payload) VALUES (?,?)',[(k,json.dumps(v)) for k,v in rows.items()])
    return rows


@pytest.mark.req('R28-REMOVED')
def test_old_impact_and_review_records_do_not_clear_or_break_staleness(tmp_path):
    repo,story=stale_book(tmp_path)
    scene=repo.list_scenes(story.id)[0]
    prose=scene.heads['prose']
    before=resolve_freshness(repo.context_view(story.id),prose)
    assert before.stale
    rows=old_records(repo,story,prose,scene.id)
    view=repo.context_view(story.id)
    after=resolve_freshness(view,prose)
    assert after.stale and [r.reason for r in after.reasons]==[r.reason for r in before.reasons]
    assert 'review_basis_changed' not in {r.reason for r in after.reasons}
    assert repo.get_version(prose).stale and repo.get_scene(scene.id).needs_review
    assert check_integrity(repo.root).ok
    backup=create_backup(repo.root,tmp_path/'backup')
    with sqlite3.connect(backup/'data'/'storygen.sqlite3') as db:
        kept={k for (k,) in db.execute('SELECT key FROM app_settings')}
    assert set(rows)<=kept


@pytest.mark.req('R28-REMOVED')
def test_get_version_without_snapshot_ignores_old_review_acceptance(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Стара'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    prose=repo.save_version(story.id,scene.id,'manual','Проза.',[]).id
    with sqlite3.connect(repo.root/'storygen.sqlite3') as db:
        db.execute('INSERT INTO app_settings(key,payload) VALUES (?,?)',(f'review3:{story.id}:acceptance:x',json.dumps({'target':{'version_id':prose}})))
    ref=repo.get_version(prose)
    assert ref.id==prose and ref.dependency_snapshot is None
