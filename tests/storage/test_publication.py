import io
import sqlite3
from importlib.resources import files

import pytest
from PIL import Image

from storygen.domain import RevisionConflict, SceneCreate, Story, StoryCreate, StorageCorruption
from storygen.generation.dependencies import save_manual_prose
from storygen.publication_models import PublicationData
from storygen.storage.repository import Repository
from storygen.storage.integrity import check_integrity


def picture(format='PNG', size=(20, 30)):
    output = io.BytesIO()
    Image.new('RGB', size, 'red').save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize('story_id',['a'*32,'old'])
def test_schema2_migration_defaults_and_old_export(tmp_path,story_id):
    root=tmp_path/'old'; root.mkdir()
    story=Story(id=story_id,title='Стара книга')
    with sqlite3.connect(root/'storygen.sqlite3') as db:
        for name in ['001_initial.sql','002_trash.sql']:
            db.executescript(files('storygen.storage').joinpath('migrations/'+name).read_text())
        db.execute('INSERT INTO stories VALUES(?,?)',(story.id,story.model_dump_json()))
        db.execute('PRAGMA user_version=2')
    assert check_integrity(root).ok
    repo=Repository(root)
    view=repo.publication('get_card',story_id=story.id)
    assert view.card.revision==0 and view.effective_title=='Стара книга'
    assert view.card.language=='uk' and not view.authors
    with repo.db.connection() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==3
        assert db.execute('SELECT COUNT(*) FROM story_publications').fetchone()[0]==0
        assert db.execute('SELECT payload FROM stories').fetchone()[0]==story.model_dump_json()


def test_card_signature_cas_archive_snapshot_and_no_prose_invalidation(tmp_path):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Назва'))
    scene=repo.create_scene(story.id,SceneCreate(title='Розділ'))
    prose=save_manual_prose(repo,scene.id,'Українська проза.',0)
    author=repo.publication('create_signature',display_name='Тінь')
    data=PublicationData(author_ids=[author.id],genres=['foreign_contemporary'],annotation='Анотація',cycle_title='Цикл',cycle_number=2)
    view=repo.publication('save_card',story_id=story.id,data=data,expected_revision=0,expected_signature_revisions={author.id:0})
    assert view.card.revision==1
    snap=repo.publication_snapshot(story.id)
    changed=repo.publication('update_signature',id=author.id,expected_revision=0,display_name='Інша тінь',archived=True)
    assert changed.revision==1 and changed.archived_at
    assert not repo.publication('list_signatures')
    assert repo.publication('get_card',story_id=story.id).authors[0].display_name=='Інша тінь'
    assert snap.publication.authors[0].display_name=='Тінь'
    assert snap.scenes[0][1].id==prose.id and not repo.get_version(prose.id).stale
    with pytest.raises(RevisionConflict):
        repo.publication('save_card',story_id=story.id,data=data,expected_revision=1,expected_signature_revisions={author.id:0})
    assert repo.publication('get_card',story_id=story.id).card.revision==1
    saved=repo.publication('save_card',story_id=story.id,data=data,expected_revision=1,expected_signature_revisions={author.id:1})
    with pytest.raises(RevisionConflict):
        repo.publication('save_card',story_id=story.id,data=data,expected_revision=1,expected_signature_revisions={author.id:1})
    other=repo.create_story(StoryCreate(title='Інше'))
    with pytest.raises(ValueError,match='архів'):
        repo.publication('save_card',story_id=other.id,data=data,expected_revision=0,expected_signature_revisions={author.id:1})
    assert saved.card.annotation=='Анотація' and check_integrity(tmp_path).ok


@pytest.mark.parametrize('data',[
    {'isbn':'1234567890'}, {'publication_date':'2026-02-30'}, {'language':'not a language'},
    {'cycle_number':1}, {'genres':['unknown']}, {'keywords':['x']*31}, {'author_ids':['bad']},
    {'cycle_title':'Цикл','cycle_number':True}, {'title':'x'*301}, {'keywords':['x','x']},
])
def test_invalid_publication_fields(data):
    with pytest.raises(ValueError): PublicationData(**data)


def test_complete_fields_roundtrip_and_isbn_normalization(tmp_path):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Назва'))
    data=PublicationData(title='Видання',annotation=' ',genres=['sf_fantasy'],keywords=['літо'],publisher='Видавець',
        isbn='978-0-306-40615-7',rights='Авторський текст',publication_date='2026-10-22',source_language='en',
        cycle_title='Цикл',cycle_number=1)
    view=repo.publication('save_card',story_id=story.id,data=data,expected_revision=0,expected_signature_revisions={})
    assert view.card.isbn=='9780306406157' and view.card.annotation=='' and view.effective_title=='Видання'
    assert Repository(tmp_path).publication('get_card',story_id=story.id).card==view.card


def test_cover_owner_hash_normalization_and_removal(tmp_path):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Книга'))
    other=repo.create_story(StoryCreate(title='Інша'))
    blob=picture()
    asset=repo.publication('upload_cover',story_id=story.id,content=blob)
    assert asset.mime_type=='image/png' and (asset.width,asset.height)==(20,30)
    assert repo.publication('read_cover',story_id=story.id,id=asset.id)[0]
    with pytest.raises(KeyError): repo.publication('read_cover',story_id=other.id,id=asset.id)
    with pytest.raises(ValueError):
        repo.publication('save_card',story_id=other.id,data=PublicationData(cover_id=asset.id),expected_revision=0,expected_signature_revisions={})
    repo.publication('save_card',story_id=story.id,data=PublicationData(cover_id=asset.id),expected_revision=0,expected_signature_revisions={})
    snap=repo.publication_snapshot(story.id)
    repo.publication('save_card',story_id=story.id,data=PublicationData(),expected_revision=1,expected_signature_revisions={})
    assert snap.publication.cover.id==asset.id and repo.files.resolve(asset.relative_path).exists()
    assert check_integrity(tmp_path).ok
    repo.files.resolve(asset.relative_path).write_bytes(b'wrong')
    with pytest.raises(StorageCorruption): repo.publication('read_cover',story_id=story.id,id=asset.id)
    assert 'hash_mismatch' in {i.code for i in check_integrity(tmp_path).issues}


@pytest.mark.parametrize('content',[b'<svg/>',b'wrong',b'x'*(10*1024*1024+1)],ids=['svg','corrupt','oversize'])
def test_reject_invalid_cover_without_asset(tmp_path,content):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Книга'))
    with pytest.raises(ValueError): repo.publication('upload_cover',story_id=story.id,content=content)
    with repo.db.connection() as db: assert db.execute('SELECT COUNT(*) FROM publication_assets').fetchone()[0]==0


def test_archived_story_blocks_publication(tmp_path):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Книга'))
    repo.set_story_trashed(story.id,0,False)
    with pytest.raises(KeyError): repo.publication('get_card',story_id=story.id)
    with pytest.raises(KeyError): repo.publication('upload_cover',story_id=story.id,content=picture())


def test_fsck_detects_publication_payload_and_foreign_asset(tmp_path):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Книга'))
    repo.publication('save_card',story_id=story.id,data=PublicationData(),expected_revision=0,expected_signature_revisions={})
    with repo.db.connection() as db: db.execute('UPDATE story_publications SET revision=99')
    assert 'invalid_publication' in {i.code for i in check_integrity(tmp_path).issues}


def test_exif_orientation_removed_and_large_or_animated_rejected(tmp_path):
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Книга'))
    output=io.BytesIO(); image=Image.new('RGB',(20,30),'red'); exif=Image.Exif();exif[274]=6;exif[270]='private'
    image.save(output,format='JPEG',exif=exif)
    cover=repo.publication('upload_cover',story_id=story.id,content=output.getvalue())
    assert (cover.width,cover.height)==(30,20)
    result=Image.open(io.BytesIO(repo.publication('read_cover',story_id=story.id,id=cover.id)[0]))
    assert not result.getexif()
    output=io.BytesIO(); Image.new('1',(4500,4500)).save(output,format='PNG')
    with pytest.raises(ValueError,match='20 мільйонів'):
        repo.publication('upload_cover',story_id=story.id,content=output.getvalue())
    output=io.BytesIO(); Image.new('RGB',(2,2),'red').save(output,format='PNG',save_all=True,append_images=[Image.new('RGB',(2,2),'blue')],duration=10)
    with pytest.raises(ValueError,match='статичне'):
        repo.publication('upload_cover',story_id=story.id,content=output.getvalue())


def test_without_pillow_metadata_still_works(tmp_path,monkeypatch):
    import builtins
    original=builtins.__import__
    def unavailable(name,*args,**kwargs):
        if name=='PIL' or name.startswith('PIL.'):raise ImportError('missing')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',unavailable)
    repo=Repository(tmp_path); story=repo.create_story(StoryCreate(title='Книга'))
    assert repo.publication('get_card',story_id=story.id).effective_title=='Книга'
    with pytest.raises(ValueError,match='Pillow'):
        repo.publication('upload_cover',story_id=story.id,content=b'not empty')
