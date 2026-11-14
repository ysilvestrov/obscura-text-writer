import sqlite3
from importlib.resources import files

import pytest

from storygen.domain import Story,StoryCreate
from storygen.storage.repository import Repository
from storygen.storage.integrity import check_integrity
from storygen.storage.backup import create_backup,restore_backup
from tests.storage.test_comments import fixture,payload,save
from storygen.authoring.comments import OriginSource


def test_schema3_migration_retains_original_payload_and_blobs(tmp_path):
    root=tmp_path/'old';root.mkdir();story=Story(id='old',title='Початковий твір')
    with sqlite3.connect(root/'storygen.sqlite3') as db:
        for name in ['001_initial.sql','002_trash.sql','003_publication.sql']:
            db.executescript(files('storygen.storage').joinpath('migrations/'+name).read_text(encoding='utf-8'))
        db.execute('INSERT INTO stories VALUES(?,?)',(story.id,story.model_dump_json()))
        db.execute('PRAGMA user_version=3')
    assert check_integrity(root).ok
    repo=Repository(root)
    with repo.db.connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==6
        assert db.execute('SELECT payload FROM stories').fetchone()[0]==story.model_dump_json()
        assert db.execute('SELECT COUNT(*) FROM authoring_comment_sets').fetchone()[0]==0
    assert check_integrity(root).ok


def test_comment_history_and_proof_survive_verified_cold_restore(tmp_path):
    repo,story,scene,version=fixture(tmp_path/'source')
    notes=payload();notes.comments[0].anchor.state='needs_review'
    notes.comments[0].anchor.origin_source=OriginSource(text='😀 Лєра була тут.')
    saved=save(repo,scene,version,notes,text='Лєра пішла.')
    assert check_integrity(repo.root).ok
    snapshot=create_backup(repo.root,tmp_path/'backup')
    restored=restore_backup(snapshot,tmp_path/'restored')
    other=Repository(restored)
    assert other.get_comment_set(scene.id)==saved['comment_set']
    assert other.get_scene(scene.id).heads['draft']==saved['version'].id
    assert check_integrity(restored).ok
    origin=other.get_comment_set(scene.id).comments[0].anchor.origin
    other.files.resolve(origin.relative_path).write_text('tampered',encoding='utf-8')
    assert not check_integrity(restored).ok


def test_comment_history_is_append_only_in_sql(tmp_path):
    repo,_,scene,version=fixture(tmp_path)
    notes=save(repo,scene,version,payload())['comment_set']
    for statement in ['UPDATE authoring_comment_sets SET payload=payload WHERE id=?','DELETE FROM authoring_comment_sets WHERE id=?']:
        with pytest.raises(sqlite3.IntegrityError):
            with repo.db.connection() as db:db.execute(statement,(notes.id,))
