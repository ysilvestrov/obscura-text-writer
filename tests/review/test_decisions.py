import pytest
from tests.review.test_runner import fixture
from storygen.generation.dependencies import save_manual_prose


def paused(root):
    values=fixture(root,concern=True);repo,story,first,second,ref,worker,run,calls=values
    worker._execute(run.id)
    return values


def test_reject_all_accepts_and_idempotent(tmp_path):
    from storygen.review.decisions import preview,decide
    repo,story,first,second,ref,worker,run,calls=paused(tmp_path)
    p=preview(repo,story.id,run.id)
    choices={c['id']:'reject' for c in p['report']['concerns']}
    result=decide(worker,story.id,run.id,p['fingerprint'],'choice-1',choices)
    assert result['state']=='queued'
    assert decide(worker,story.id,run.id,p['fingerprint'],'choice-1',choices)==result
    assert not repo.get_version(ref.id).stale
    assert len(calls)==4  # prefix memory + delta/check/synthesis
    worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert sum(c.stage=='review_part' for c in calls)==3


def test_selected_fixes_wait_then_finish_without_search(tmp_path):
    from storygen.review.decisions import preview,decide,finish
    repo,story,first,second,ref,worker,run,calls=paused(tmp_path);p=preview(repo,story.id,run.id)
    decide(worker,story.id,run.id,p['fingerprint'],'choice-1',{c['id']:'fix' for c in p['report']['concerns']})
    assert repo.get_run(run.id).impact['phase']=='author_editing'
    save_manual_prose(repo,second.id,'Марія побачила лист.',repo.get_scene(second.id).revision)
    p=preview(repo,story.id,run.id)
    finish(worker,story.id,run.id,p['fingerprint'],'finish-1')
    worker._execute(run.id)
    assert repo.get_run(run.id).state=='completed'
    assert sum(c.stage=='review_part' for c in calls)==3
    assert not repo.get_version(repo.get_scene(second.id).heads['prose']).stale


def test_stale_or_foreign_decision_rejected(tmp_path):
    from storygen.review.decisions import preview,decide
    repo,story,first,second,ref,worker,run,calls=paused(tmp_path);p=preview(repo,story.id,run.id)
    with pytest.raises(ValueError):preview(repo,'foreign',run.id)
    save_manual_prose(repo,second.id,'Змінений текст.',repo.get_scene(second.id).revision)
    with pytest.raises(ValueError):decide(worker,story.id,run.id,p['fingerprint'],'stale',{c['id']:'reject' for c in p['report']['concerns']})


def test_refreshed_preview_does_not_hide_external_edit_while_waiting(tmp_path):
    from storygen.review.decisions import preview,decide
    repo,story,first,second,ref,worker,run,calls=paused(tmp_path)
    save_manual_prose(repo,second.id,'Зовнішній текст після пошуку.',repo.get_scene(second.id).revision)
    p=preview(repo,story.id,run.id)
    with pytest.raises(ValueError):decide(worker,story.id,run.id,p['fingerprint'],'external-new-preview',{c['id']:'reject' for c in p['report']['concerns']})
    assert p['changed_while_waiting']
