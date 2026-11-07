import hashlib
import pytest
from storygen.domain import StoryCreate, SceneCreate, RevisionConflict, new_id
from storygen.import_models import ImportPublication, ImportedScene
from storygen.storage.repository import Repository


def prepared(repo,story,text='Сцена 1: Ранок\nОпис'):
    raw=text.encode();version=repo.save_version(story.id,None,'source_plan',text,[])
    metadata=dict(id=new_id(),name='plan.md',kind='source_plan',version_id=version.id,relative_path='stories/'+story.id+'/sources/'+new_id()+'.bin',sha256=hashlib.sha256(raw).hexdigest())
    repo.files.write(metadata['relative_path'],raw)
    return ImportPublication(metadata=metadata,active_plan_version_id=version.id)


def test_cas_and_journal_do_not_replace_active_source(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    first=prepared(repo,story);repo.publish_import(story.id,story.revision,first)
    stale=prepared(repo,story,'Інший')
    with pytest.raises(RevisionConflict):repo.publish_import(story.id,story.revision,stale)
    assert len(repo.list_source_files(story.id))==1
    revision=repo.get_story(story.id).revision
    stale.active_plan_version_id=None
    repo.publish_import(story.id,revision,stale)
    assert repo.active_source(story.id,'source_plan').id==first.active_plan_version_id
    assert repo.context_view(story.id).active_source(story.id,'source_plan').id==first.active_plan_version_id
    assert len(repo.list_source_files(story.id))==2


def test_publication_rolls_back_after_first_scene(tmp_path,monkeypatch):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'))
    change=prepared(repo,story)
    for n in [1,2]:
        text=f'Сцена {n}: Опис'
        ref=repo.save_version(story.id,None,'scene_plan',text,[change.metadata['version_id']])
        change.scenes.append(ImportedScene(data=SceneCreate(title='Опис',beats=text,author_scene_number=n),plan_version_id=ref.id))
    from storygen.storage import scene_metadata
    original=scene_metadata.apply_description
    count=0
    def fail(*args,**kwargs):
        nonlocal count
        count+=1
        if count==2:raise ValueError('synthetic fault')
        return original(*args,**kwargs)
    monkeypatch.setattr(scene_metadata,'apply_description',fail)
    with pytest.raises(ValueError,match='synthetic fault'):repo.publish_import(story.id,story.revision,change)
    assert count==2
    assert repo.list_scenes(story.id)==[]
    assert repo.list_source_files(story.id)==[]
    assert repo.active_source(story.id,'source_plan') is None


def test_schema4_backfill_preserves_latest_selector_and_explicit_number(tmp_path):
    import json
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Старий'))
    first=prepared(repo,story);repo.register_source(story.id,first.metadata)
    last=prepared(repo,story,'Сцена 2: Друга');repo.register_source(story.id,last.metadata)
    scene=repo.create_scene(story.id,SceneCreate(title='Друга',beats='Сцена 2: Друга'))
    with repo.db.connection() as db:
        data=scene.model_dump();data.pop('author_scene_number')
        db.execute('UPDATE scenes SET payload=? WHERE id=?',(json.dumps(data),scene.id))
        db.execute('DROP TABLE active_sources');db.execute('PRAGMA user_version=4')
    copy=Repository(tmp_path)
    assert copy.active_source(story.id,'source_plan').id==last.metadata['version_id']
    assert copy.get_scene(scene.id).author_scene_number==2
    assert copy.read_text(first.metadata['version_id'])=='Сцена 1: Ранок\nОпис'
    from storygen.storage.integrity import check_integrity
    assert check_integrity(tmp_path).ok
