import pytest
from storygen.generation.rewrite_review import rewrite_preview,apply_selection
from storygen.authoring.comments import CommentPayload
from storygen.domain import RevisionConflict


def apply(repo,scene,attempt,indices=None):
    p=rewrite_preview(repo,scene.id,attempt.id)
    if indices is None:indices=list(range(len(p['edits'])))
    return apply_selection(repo,scene.id,attempt.id,indices,p['expected_revision'],p['proposal_fingerprint'],p['expected_comments_revision'])


def test_accept_rewrite_draft_is_current_and_notes_clear(rewrite_proposal):
    repo,scene,source,notes,attempt=rewrite_proposal
    prose=repo.save_version(scene.story_id,scene.id,'manual','Проза лишається.',[])
    repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
    result=apply(repo,scene,attempt)
    current=repo.get_version(result['version'].id)
    assert current.kind=='draft' and not current.stale
    assert repo.get_scene(scene.id).heads['prose']==prose.id
    assert repo.get_scene(scene.id).heads['draft']==current.id
    assert repo.get_comment_set(scene.id).comments==[] and repo.get_comment_set(scene.id).general==''
    assert repo.get_comment_set(scene.id,notes.id).general==notes.general
    assert result['attempt'].context['rewrite_decisions'][-1]['selected_indices']


def test_reject_all_keeps_source_and_notes_without_new_version(rewrite_proposal):
    repo,scene,source,notes,attempt=rewrite_proposal
    before=len(repo.list_versions(scene.story_id,scene.id))
    result=apply(repo,scene,attempt,[])
    assert result['version'] is None
    assert len(repo.list_versions(scene.story_id,scene.id))==before
    assert repo.get_scene(scene.id).heads['draft']==source.id
    assert repo.get_comment_set(scene.id).id==notes.id
    assert result['attempt'].context['rewrite_decisions'][-1]['selected_indices']==[]


def test_changed_notes_do_not_get_cleared(rewrite_proposal):
    repo,scene,source,notes,attempt=rewrite_proposal
    p=rewrite_preview(repo,scene.id,attempt.id)
    repo.save_draft_with_comments(scene.id,repo.read_text(source.id),'markdown',scene.revision,notes.revision,CommentPayload(general='Інша вкладка.'),expected_source_version_id=source.id)
    with pytest.raises((ValueError,RevisionConflict)):
        apply_selection(repo,scene.id,attempt.id,list(range(len(p['edits']))),p['expected_revision'],p['proposal_fingerprint'],notes.revision)
    assert repo.get_comment_set(scene.id).general=='Інша вкладка.'
    assert repo.get_scene(scene.id).heads['draft']==source.id


def test_notes_insert_failure_rolls_back_draft_decision_and_catalog(rewrite_proposal,monkeypatch):
    import storygen.storage.rewrite_store as store
    repo,scene,source,notes,attempt=rewrite_proposal
    before=len(repo.list_versions(scene.story_id,scene.id))
    def fail(*_):raise ValueError('injected failure')
    monkeypatch.setattr(store,'_insert_comment_set',fail)
    with pytest.raises(ValueError,match='injected'):apply(repo,scene,attempt)
    assert repo.get_scene(scene.id).heads['draft']==source.id
    assert repo.get_comment_set(scene.id).id==notes.id
    assert len(repo.list_versions(scene.story_id,scene.id))==before
    assert not repo.get_attempt(attempt.id).context.get('rewrite_decisions')


def test_partial_apply_and_second_application_is_blocked(rewrite_proposal):
    repo,scene,source,notes,attempt=rewrite_proposal
    p=rewrite_preview(repo,scene.id,attempt.id)
    result=apply(repo,scene,attempt,p['groups'][0]['indices'])
    assert not repo.get_version(result['version'].id).stale
    assert repo.read_text(result['version'].id)!=repo.read_text(source.id)
    with pytest.raises(ValueError):apply(repo,scene,attempt)


def test_identical_text_new_head_id_blocks_old_proposal(rewrite_proposal):
    repo,scene,source,notes,attempt=rewrite_proposal
    other=repo.save_version(scene.story_id,scene.id,'draft',repo.read_text(source.id),[],content_format=source.content_format)
    repo.set_head(scene.id,'draft',other.id,scene.revision)
    assert not rewrite_preview(repo,scene.id,attempt.id)['can_apply']
    with pytest.raises(ValueError):apply(repo,scene,attempt)


def test_note_race_during_result_blob_write_preserves_other_tab(rewrite_proposal,monkeypatch):
    repo,scene,source,notes,attempt=rewrite_proposal
    original_write=repo.files.write;done=False
    def write(path,raw):
        nonlocal done
        result=original_write(path,raw)
        if not done:
            done=True
            repo.save_draft_with_comments(scene.id,repo.read_text(source.id),'markdown',scene.revision,notes.revision,CommentPayload(general='Зберегти цю вказівку.'),expected_source_version_id=source.id)
        return result
    monkeypatch.setattr(repo.files,'write',write)
    with pytest.raises(RevisionConflict):apply(repo,scene,attempt)
    assert repo.get_comment_set(scene.id).general=='Зберегти цю вказівку.'
    assert repo.get_scene(scene.id).heads['draft']==source.id
    assert not repo.get_attempt(attempt.id).context.get('rewrite_decisions')
