import io
import sqlite3
from importlib.resources import files

from PIL import Image
import pytest

from storygen.domain import Story, StoryCreate
from storygen.publication_models import PublicationData
from storygen.storage.repository import Repository
from storygen.storage.backup import create_backup, restore_backup
from storygen.storage.integrity import check_integrity
from storygen.storage.integrity import readonly_database


@pytest.mark.parametrize('schema',[2,3])
def test_publication_cold_backup_restore_schema2_and_3(tmp_path,schema):
    source=tmp_path/'source'
    if schema==2:
        source.mkdir(); story=Story(id='b'*32,title='Стара')
        with sqlite3.connect(source/'storygen.sqlite3') as db:
            for name in ['001_initial.sql','002_trash.sql']:
                db.executescript(files('storygen.storage').joinpath('migrations/'+name).read_text())
            db.execute('PRAGMA user_version=2')
            db.execute('INSERT INTO stories VALUES(?,?)',(story.id,story.model_dump_json()))
    else:
        repo=Repository(source); story=repo.create_story(StoryCreate(title='Книга'))
        author=repo.publication('create_signature',display_name='Псевдонім')
        blob=io.BytesIO(); Image.new('RGB',(8,10)).save(blob,format='PNG')
        cover=repo.publication('upload_cover',story_id=story.id,content=blob.getvalue())
        repo.publication('save_card',story_id=story.id,data=PublicationData(author_ids=[author.id],cover_id=cover.id),expected_revision=0,expected_signature_revisions={author.id:0})
        repo.publication('update_signature',id=author.id,expected_revision=0,archived=True)
    backup=create_backup(source,tmp_path/'backup')
    from contextlib import closing
    with closing(readonly_database(backup/'data/storygen.sqlite3')) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==schema
    restored=restore_backup(backup,tmp_path/'restored')
    assert check_integrity(restored).ok
    view=Repository(restored).publication('get_card',story_id=story.id)
    if schema==3:
        assert view.authors[0].display_name=='Псевдонім' and view.authors[0].archived_at
        assert view.cover.sha256==cover.sha256
    else:assert view.card.revision==0
