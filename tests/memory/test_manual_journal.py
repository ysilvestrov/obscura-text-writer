import json
import pytest
from storygen.domain import StoryCreate,SceneCreate,RevisionConflict
from storygen.storage.repository import Repository
from storygen.memory.models import MemorySnapshot,MemoryEntry
from storygen.memory.journal import load_memory


def workspace(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Ручна пам’ять'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i))) for i in range(2)]
    ids=[]
    for i,scene in enumerate(scenes):
        ref=repo.save_version(story.id,scene.id,'manual',f'Доказ {i}.',[])
        repo.set_head(scene.id,'prose',ref.id,0);ids.append(ref.id)
    old=MemorySnapshot(facts=[MemoryEntry(text='Перший факт',source_version_id=ids[0],quote='Доказ 0.')],source_prose_ids=ids[:1])
    ref=repo.save_version(story.id,scenes[0].id,'memory',old.model_dump_json(),ids[:1])
    repo.set_head(scenes[0].id,'memory',ref.id,1)
    return repo,story,scenes,ids,old


def test_manual_v1_normalizes_to_v2_and_retains_previous_events(tmp_path):
    from storygen.memory.service import save_scene_memory
    repo,story,scenes,ids,old=workspace(tmp_path)
    data=old.model_copy(deep=True);data.source_prose_ids=ids
    data.timeline.append(MemoryEntry(text='Подія 2',source_version_id=ids[1],quote='Доказ 1.'))
    ref=save_scene_memory(repo,scenes[1].id,data.model_dump_json(),1)
    result=load_memory(repo.read_text(ref.id))
    assert result.events[:1]==load_memory(old.model_dump_json()).events
    assert result.schema_version==2 and ref.dependency_snapshot is not None
    assert repo.get_scene(scenes[1].id).heads['memory']==ref.id


def test_manual_cannot_rewrite_previous_prefix_even_with_valid_quote(tmp_path):
    from storygen.memory.service import save_scene_memory
    repo,story,scenes,ids,old=workspace(tmp_path)
    value=load_memory(old.model_dump_json()).model_dump();value['source_prose_ids']=ids
    value['events'][0]['text']='Інший висновок'
    with pytest.raises(ValueError,match='попередніх'):
        save_scene_memory(repo,scenes[1].id,json.dumps(value),1)
    assert 'memory' not in repo.get_scene(scenes[1].id).heads


def test_revision_checked_before_normalization_and_future_source_rejected(tmp_path):
    from storygen.memory.service import save_scene_memory
    repo,story,scenes,ids,old=workspace(tmp_path)
    with pytest.raises(RevisionConflict):save_scene_memory(repo,scenes[1].id,'bad JSON',0)
    future=MemorySnapshot(source_prose_ids=[ids[1]])
    with pytest.raises(ValueError):save_scene_memory(repo,scenes[0].id,future.model_dump_json(),2)


def test_fsck_checks_evidence_without_treating_reorder_as_corruption(tmp_path):
    from storygen.memory.service import save_scene_memory
    from storygen.storage.integrity import check_integrity
    repo,story,scenes,ids,old=workspace(tmp_path)
    value=old.model_copy(deep=True);value.source_prose_ids=ids
    save_scene_memory(repo,scenes[1].id,value.model_dump_json(),1)
    repo.reorder_scenes(story.id,[s.id for s in reversed(scenes)],repo.get_story(story.id).revision)
    assert check_integrity(tmp_path).ok
    bad=load_memory(old.model_dump_json()).model_dump();bad['events'][0]['quote']='Відсутній доказ'
    repo.save_version(story.id,scenes[0].id,'memory',json.dumps(bad),ids[:1])
    assert 'invalid_memory' in {issue.code for issue in check_integrity(tmp_path).issues}
