import pytest

from storygen.domain import StoryCreate, SceneCreate, RevisionConflict, StorageCorruption
from storygen.storage.repository import Repository


def setup_story(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title="Двері"))
    scene = repo.create_scene(story.id, SceneCreate(title="Ранок", beats="Огляд бібліотеки"))
    return repo, story, scene


def test_versions_survive_reopen(tmp_path):
    repo, story, scene = setup_story(tmp_path)
    first = repo.save_version(story.id, scene.id, "manual", "Перший текст", [])
    scene = repo.set_head(scene.id,"prose",first.id,scene.revision)
    second = repo.save_version(story.id,scene.id,"manual","Другий текст",[first.id])
    repo.set_head(scene.id,"prose",second.id,scene.revision)
    other = Repository(tmp_path)
    assert other.read_text(first.id) == "Перший текст"
    assert other.get_scene(scene.id).heads["prose"] == second.id


def test_stale_revision_cannot_replace_head(tmp_path):
    repo, story, scene = setup_story(tmp_path)
    version = repo.save_version(story.id,scene.id,"manual","Новий текст",[])
    repo.set_head(scene.id,"prose",version.id,scene.revision)
    with pytest.raises(RevisionConflict):
        repo.set_head(scene.id,"prose",version.id,scene.revision)


def test_failed_file_write_never_creates_current(tmp_path,monkeypatch):
    repo, story, scene = setup_story(tmp_path)
    def fail(*args,**kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(repo.files,"write",fail)
    with pytest.raises(OSError):
        repo.save_version(story.id,scene.id,"manual","Не записано",[])
    assert not repo.get_scene(scene.id).heads


def test_missing_or_modified_blob_reports_corruption(tmp_path):
    repo, story, scene = setup_story(tmp_path)
    version=repo.save_version(story.id,scene.id,"manual","Оригінал",[])
    (tmp_path/version.relative_path).write_text("Підміна",encoding="utf-8")
    with pytest.raises(StorageCorruption):
        repo.read_text(version.id)
