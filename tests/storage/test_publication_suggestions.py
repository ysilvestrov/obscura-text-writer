import pytest
from storygen.domain import RevisionConflict, StoryCreate
from storygen.publication_models import PublicationData
from storygen.generation.dependencies import save_manual_prose
from tests.generation.test_publication_metadata import seeded,run_proposal
from storygen.generation.publication_metadata import suggestions_state


def acceptance(repo,story):
    proposal=suggestions_state(repo,story.id)['proposals'][0]
    return {'attempt_id':proposal['attempt_id'],'fingerprint':proposal['fingerprint'],'fields':['annotation']}


def test_save_suggestion_only_explicit_fields_and_atomic_checks(tmp_path):
    repo,story=seeded(tmp_path);run_proposal(repo,story);accepted=acceptance(repo,story)
    result=repo.publication('save_card',story_id=story.id,data=PublicationData(annotation='Відредагована автором анотація.'),expected_revision=0,expected_signature_revisions={},suggestion=accepted)
    assert result.card.annotation.startswith('Відредагована') and not result.card.genres
    assert not repo.list_versions(story.id,kind='brief')
    with pytest.raises(RevisionConflict):
        repo.publication('save_card',story_id=story.id,data=PublicationData(annotation='Заміна'),expected_revision=1,expected_signature_revisions={},suggestion=accepted)
    assert repo.publication('get_card',story_id=story.id).card.revision==1


@pytest.mark.parametrize('change',['prose','title','fingerprint','owner','fields','cancelled'])
def test_stale_or_forged_proposal_cannot_be_saved(tmp_path,change):
    repo,story=seeded(tmp_path);run_proposal(repo,story);accepted=acceptance(repo,story)
    target=story.id
    if change=='prose':
        scene=repo.list_scenes(story.id)[0];save_manual_prose(repo,scene.id,'Інший текст.',repo.get_scene(scene.id).revision)
    elif change=='title':
        scene=repo.list_scenes(story.id)[0];repo.update_scene_metadata(scene.id,{'title':'Інша назва'},scene.revision)
    elif change=='fingerprint':accepted['fingerprint']='forged'
    elif change=='owner':target=repo.create_story(StoryCreate(title='Інша')).id
    elif change=='fields':accepted['fields']=['rights']
    elif change=='cancelled':
        attempt=repo.get_attempt(accepted['attempt_id']);run=repo.get_run(attempt.run_id)
        run.state='cancelled';repo.save_run(run)
    with pytest.raises((ValueError,RevisionConflict)):
        repo.publication('save_card',story_id=target,data=PublicationData(annotation='Текст'),expected_revision=0,expected_signature_revisions={},suggestion=accepted)
    assert repo.publication('get_card',story_id=target).card.revision==0
