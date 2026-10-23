import json
import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.memory.test_forwarding import seeded


@pytest.mark.parametrize('kind',['plan','brief','draft','prose','memory'])
def test_unchanged_scene_save_preserves_versions_revisions_and_dependents(tmp_path,kind):
    repo,story,scenes=seeded(tmp_path)
    scene=repo.get_scene(scenes[0].id)
    version_kind={'plan':'scene_plan','brief':'brief','draft':'draft','prose':'manual','memory':'memory'}[kind]
    text=json.dumps({'objective':'Мета','beats':['Подія'],'constraints':[],'proposed_changes':[]}) if kind=='brief' else scene.beats if kind=='plan' else 'Збережений текст' if kind=='draft' else repo.read_text(scene.heads[kind])
    if kind in {'plan','brief','draft'}:
        ref=repo.save_version(story.id,scene.id,version_kind,text,[])
        scene=repo.set_head(scene.id,kind,ref.id,scene.revision)
    # A downstream selected version explicitly depends on the saved head.
    later=repo.get_scene(scenes[-1].id)
    dependent=repo.save_version(story.id,later.id,'draft','Наступна сцена',[scene.heads[kind]])
    repo.set_head(later.id,'draft',dependent.id,later.revision)
    before=repo.get_scene(scene.id);story_before=repo.get_story(story.id)
    all_before=[s.model_dump() for s in repo.list_scenes(story.id)]
    versions_before=[v.model_dump() for v in repo.list_versions(story.id)]
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        method='patch' if kind=='plan' else 'post'
        endpoint=f'/api/scenes/{scene.id}' if kind=='plan' else f'/api/scenes/{scene.id}/{kind}'
        payload={'story_id':story.id,'beats':text,'expected_revision':before.revision} if kind=='plan' else {'text':text,'expected_revision':before.revision}
        result=getattr(client,method)(endpoint,json=payload)
        assert result.status_code==200,result.text
        assert repo.get_story(story.id)==story_before
        assert [s.model_dump() for s in repo.list_scenes(story.id)]==all_before
        assert [v.model_dump() for v in repo.list_versions(story.id)]==versions_before
        payload['expected_revision']-=1
        assert getattr(client,method)(endpoint,json=payload).status_code==409


def test_same_head_and_metadata_are_noops_with_cas(tmp_path):
    from storygen.domain import RevisionConflict
    repo,story,scenes=seeded(tmp_path);scene=repo.get_scene(scenes[0].id)
    before=repo.get_story(story.id)
    assert repo.set_head(scene.id,'prose',scene.heads['prose'],scene.revision)==scene
    assert repo.update_scene_metadata(scene.id,{'title':scene.title,'target_words':scene.target_words,'character_ids':scene.character_ids},scene.revision)==scene
    assert repo.get_story(story.id)==before
    with pytest.raises(RevisionConflict):repo.set_head(scene.id,'prose',scene.heads['prose'],scene.revision-1)


def test_unchanged_stale_draft_is_not_rebased_or_accepted(tmp_path):
    from storygen.generation.dependencies import save_manual_draft
    repo,story,scenes=seeded(tmp_path);scene=repo.get_scene(scenes[0].id)
    draft=repo.save_version(story.id,scene.id,'draft','Чернетка',[scene.heads['prose']])
    scene=repo.set_head(scene.id,'draft',draft.id,scene.revision)
    repo.invalidate_dependents([scene.heads['prose']])
    before=repo.get_scene(scene.id)
    saved=save_manual_draft(repo,scene.id,'Чернетка',before.revision)
    assert saved.id==draft.id and saved.stale
    assert repo.get_scene(scene.id)==before
    assert not repo.list_acceptances(story.id)


def test_changed_text_still_invalidates_dependents(tmp_path):
    from storygen.generation.dependencies import save_manual_prose
    repo,story,scenes=seeded(tmp_path);scene=repo.get_scene(scenes[0].id)
    previous=scene.heads['prose']
    later=repo.get_scene(scenes[-1].id)
    dependent=repo.save_version(story.id,later.id,'draft','Пізніша сцена',[previous])
    repo.set_head(later.id,'draft',dependent.id,later.revision)
    saved=save_manual_prose(repo,scene.id,repo.read_text(previous)+' ',scene.revision)
    assert saved.id!=previous
    assert repo.get_version(dependent.id).stale
    assert repo.get_scene(later.id).needs_review
