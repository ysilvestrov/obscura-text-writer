import json
import sqlite3
import pytest
from storygen.domain import StoryCreate, SceneCreate, RevisionConflict
from storygen.storage.repository import Repository


def setup(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Твір'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i))) for i in range(3)]
    return repo,story,scenes


def test_scene_trash_restore_preserves_text_and_invalidates_later(tmp_path):
    from storygen.authoring.trash import trash_scene, restore_scene
    repo,story,scenes=setup(tmp_path)
    refs=[repo.save_version(story.id,s.id,'manual','Текст '+s.title,[]) for s in scenes]
    for scene,ref in zip(scenes,refs):repo.set_head(scene.id,'prose',ref.id,0)
    scene=repo.get_scene(scenes[1].id)
    removed=trash_scene(repo,story.id,scene.id,scene.revision)
    assert [s.id for s in repo.list_scenes(story.id)]==[scenes[0].id,scenes[2].id]
    with pytest.raises(KeyError):repo.get_scene(scene.id)
    with pytest.raises(KeyError):repo.read_text(refs[1].id)
    assert repo.get_scene(scenes[2].id).needs_review
    assert repo.get_version(refs[2].id).stale
    assert (repo.root/refs[1].relative_path).read_text(encoding='utf-8')=='Текст 1'
    with pytest.raises(RevisionConflict):restore_scene(repo,story.id,scene.id,scene.revision)
    restored=restore_scene(repo,story.id,scene.id,removed.revision)
    assert restored.trashed_at is None
    assert [s.id for s in repo.list_scenes(story.id)]==[s.id for s in scenes]
    assert repo.read_text(refs[1].id)=='Текст 1'
    assert [s.position for s in repo.list_scenes(story.id)]==[0,1,2]


def test_story_trash_is_reversible_and_rejects_active_reads(tmp_path):
    from storygen.authoring.trash import trash_story, restore_story
    repo,story,scenes=setup(tmp_path)
    ref=repo.save_version(story.id,scenes[0].id,'manual','Оригінал',[])
    story=repo.get_story(story.id)
    removed=trash_story(repo,story.id,story.revision)
    assert repo.list_stories()==[]
    assert repo.list_stories(include_trashed=True)[0].trashed_at
    for read in [lambda:repo.get_story(story.id),lambda:repo.get_scene(scenes[0].id),lambda:repo.read_text(ref.id)]:
        with pytest.raises(KeyError):read()
    restore_story(repo,story.id,removed.revision)
    assert repo.read_text(ref.id)=='Оригінал'


@pytest.mark.parametrize('state',['queued','running','paused','interrupted','needs_review','alternative','pause_requested','cancellation_requested'])
def test_trash_rejects_resumable_runs(tmp_path,state):
    from storygen.authoring.trash import trash_story, trash_scene
    repo,story,scenes=setup(tmp_path)
    with repo.db.connection() as db:
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?)',('run',story.id,'request',state,json.dumps({})))
    with pytest.raises(ValueError,match='запуск'):trash_story(repo,story.id,repo.get_story(story.id).revision)
    with pytest.raises(ValueError,match='запуск'):trash_scene(repo,story.id,scenes[0].id,0)
    assert len(repo.list_scenes(story.id))==3


def test_scene_ownership_and_revision_guard(tmp_path):
    from storygen.authoring.trash import trash_scene
    repo,story,scenes=setup(tmp_path)
    other=repo.create_story(StoryCreate(title='Інший'))
    with pytest.raises(ValueError):trash_scene(repo,other.id,scenes[0].id,0)
    with pytest.raises(RevisionConflict):trash_scene(repo,story.id,scenes[0].id,99)
    assert len(repo.list_scenes(story.id))==3


def test_existing_database_migrates_without_changing_content(tmp_path):
    from importlib.resources import files
    path=tmp_path/'storygen.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(files('storygen.storage').joinpath('migrations/001_initial.sql').read_text())
        db.execute('PRAGMA user_version=1')
        payload={'id':'old','title':'Старий твір','revision':7}
        db.execute('INSERT INTO stories VALUES(?,?)',('old',json.dumps(payload)))
    repo=Repository(tmp_path)
    assert repo.get_story('old').revision==7
    assert repo.get_story('old').trashed_at is None
    with repo.db.connection() as db:assert db.execute('PRAGMA user_version').fetchone()[0]==3
