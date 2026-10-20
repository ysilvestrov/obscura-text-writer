import pytest
from storygen.domain import StoryCreate, RevisionConflict
from storygen.storage.repository import Repository
from storygen.authoring.blueprints import parse_blueprint, apply_blueprint


def test_blueprint_is_proposal_until_apply(tmp_path):
    repo=Repository(tmp_path)
    story=repo.create_story(StoryCreate(title='Пропозиція'))
    proposal=parse_blueprint('{"canon":"Лєра фотографка", "characters":[], "scenes":[{"title":"Ранок", "beats":"Студія"}], "warnings":["Перевірити освіту"]}')
    assert repo.get_story(story.id).canon_version_id is None
    applied=apply_blueprint(repo,story.id,proposal,story.revision)
    assert repo.read_text(applied.canon_version_id)=='Лєра фотографка'
    assert repo.list_scenes(story.id)[0].title=='Ранок'
    with pytest.raises(RevisionConflict): apply_blueprint(repo,story.id,proposal,story.revision)
