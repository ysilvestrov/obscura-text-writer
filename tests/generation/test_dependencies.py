from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose, select_prose


def test_edit_scene_two_invalidates_downstream_not_other_story(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Перший'));other=repo.create_story(StoryCreate(title='Другий'))
    a=repo.create_scene(story.id,SceneCreate(title='Два'));b=repo.create_scene(story.id,SceneCreate(title='Три'))
    original=save_manual_prose(repo,a.id,'Старий текст',0)
    mem=repo.save_version(story.id,a.id,'memory','{}',[original.id]);repo.set_head(a.id,'memory',mem.id,1)
    downstream=repo.save_version(story.id,b.id,'edited','Третя сцена',[mem.id]);repo.set_head(b.id,'prose',downstream.id,0)
    untouched=repo.save_version(other.id,None,'canon','Інший твір',[])
    new=save_manual_prose(repo,a.id,'Авторська нова правка',2)
    assert repo.get_version(mem.id).stale and repo.get_version(downstream.id).stale
    assert repo.get_scene(b.id).needs_review
    assert repo.read_text(downstream.id)=='Третя сцена'
    assert not repo.get_version(untouched.id).stale
    assert repo.get_scene(a.id).heads['prose']==new.id


def test_reselecting_older_prose_changes_memory_source(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'));scene=repo.create_scene(story.id,SceneCreate(title='Один'))
    old=save_manual_prose(repo,scene.id,'Старий',0)
    new=save_manual_prose(repo,scene.id,'Новий',1)
    selected=select_prose(repo,scene.id,old.id,2)
    assert selected.heads['prose']==old.id
    assert repo.read_text(new.id)=='Новий'
