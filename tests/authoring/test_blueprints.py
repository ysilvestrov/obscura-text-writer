import json
import pytest
from storygen.domain import StoryCreate, RevisionConflict
from storygen.storage.repository import Repository
from storygen.authoring.blueprints import parse_blueprint, apply_blueprint


def test_blueprint_is_proposal_until_apply(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Пропозиція'))
    proposal=parse_blueprint('{"canon":"Олена фотографка", "characters":[], "scenes":[{"title":"Ранок", "beats":"Студія"}], "warnings":["Перевірити освіту"]}')
    assert repo.get_story(story.id).canon_version_id is None
    applied=apply_blueprint(repo,story.id,proposal,story.revision)
    assert repo.read_text(applied.canon_version_id)=='Олена фотографка'
    assert repo.list_scenes(story.id)[0].title=='Ранок'
    with pytest.raises(RevisionConflict): apply_blueprint(repo,story.id,proposal,story.revision)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_blueprint_prose_source_is_not_a_dependency(tmp_path):
    from storygen.domain import SceneCreate
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Проза'))
    scene=repo.create_scene(story.id,SceneCreate(title='С',beats='Б'))
    prose=repo.save_version(story.id,scene.id,'manual','Іва-Швидка прийшла.',[])
    plan=repo.save_version(story.id,None,'source_plan','Іва — героїня.',[])
    proposal=parse_blueprint(json.dumps({'canon':'К','characters':[{'id':'c','name':'Іва','description':'Д','sources':[
        {'version_id':prose.id,'quote':'Іва-Швидка'},{'version_id':plan.id,'quote':'героїня'}]}],
        'scenes':[{'title':'Ранок','beats':'Студія'}]},ensure_ascii=False))
    applied=apply_blueprint(repo,story.id,proposal,repo.get_story(story.id).revision)
    assert repo.get_version(applied.characters_version_id).input_refs==[plan.id]
    assert repo.get_version(applied.canon_version_id).input_refs==[plan.id]
