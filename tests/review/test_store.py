import pytest
from storygen.domain import new_id
from storygen.run_models import Run,RunRequest
from storygen.impact.planning import capture_target
from tests.impact.test_runner import runner


def setup(root):
    repo,story,first,second,ref,worker,old,_=runner(root)
    worker.cancel(old.id)
    run=Run(id=new_id(),story_id=story.id,request_id=new_id(),request=RunRequest(story_id=story.id,mode='impact'),tasks=[],impact=dict(protocol=3,scene_order=[s.id for s in repo.list_scenes(story.id)],scene_cursor=1,phase='awaiting_author'))
    repo.enqueue_run(run)
    target=capture_target(repo.context_view(story.id),ref.id)
    return repo,story,first,second,ref,run,target


def report_for(repo,run,target):
    from storygen.review.models import SceneReport
    report=SceneReport(story_id=run.story_id,run_id=run.id,scene_id=target.scene_id,targets=[target],complete=True)
    return report


def test_author_acceptance_is_bound_to_exact_sources(tmp_path):
    from storygen.review.store import publish_scene
    from storygen.generation.dependencies import save_manual_prose
    repo,story,first,second,ref,run,target=setup(tmp_path)
    report=report_for(repo,run,target)
    assert repo.get_version(ref.id).stale
    result=publish_scene(repo,run.id,report,'author_rejected','operation-one')
    assert result['acceptances'][0]['authority']=='author_rejected'
    assert not repo.get_version(ref.id).stale
    assert not repo.get_scene(second.id).needs_review
    save_manual_prose(repo,first.id,'Марія не знає про лист.',repo.get_scene(first.id).revision)
    assert repo.get_version(ref.id).stale


def test_operation_id_is_idempotent_and_rejects_payload_collision(tmp_path):
    from storygen.review.store import publish_scene
    repo,story,first,second,ref,run,target=setup(tmp_path);report=report_for(repo,run,target)
    first=publish_scene(repo,run.id,report,'author_rejected','operation-one')
    assert publish_scene(repo,run.id,report,'author_rejected','operation-one')==first
    with pytest.raises(ValueError):publish_scene(repo,run.id,report,'author_revised','operation-one')


def test_foreign_or_changed_head_cannot_accept(tmp_path):
    from storygen.review.store import publish_scene
    from storygen.generation.dependencies import save_manual_prose
    repo,story,first,second,ref,run,target=setup(tmp_path);report=report_for(repo,run,target)
    save_manual_prose(repo,second.id,'Інший авторський текст.',repo.get_scene(second.id).revision)
    with pytest.raises(ValueError):publish_scene(repo,run.id,report,'author_rejected','operation-one')
    foreign=report.model_copy(update={'story_id':'foreign'})
    with pytest.raises(ValueError):publish_scene(repo,run.id,foreign,'author_rejected','operation-two')


def test_automatic_acceptance_requires_real_proof(tmp_path):
    from storygen.review.store import publish_scene
    repo,story,first,second,ref,run,target=setup(tmp_path);report=report_for(repo,run,target)
    with pytest.raises(ValueError):publish_scene(repo,run.id,report,'model_no_concerns','operation-one')
    assert repo.get_version(ref.id).stale


def test_author_acceptance_does_not_rewrite_model_report(tmp_path):
    from storygen.review.store import publish_scene
    from storygen.review.models import Concern
    from storygen.storage.context_view import ContextView
    repo,story,first,second,ref,run,target=setup(tmp_path);report=report_for(repo,run,target)
    report.concerns=[Concern(id='Q1',kind='issue',message='Автор вважає зауваження нерелевантним.')]
    publish_scene(repo,run.id,report,'author_rejected','operation-one')
    view=repo.context_view(story.id)
    assert view.review_reports[report.id].concerns==report.concerns
    assert not view.get_version(ref.id).stale


def test_acceptance_payload_tampering_is_not_authority(tmp_path):
    import json
    from storygen.review.store import publish_scene,prefix
    repo,story,first,second,ref,run,target=setup(tmp_path);report=report_for(repo,run,target)
    saved=publish_scene(repo,run.id,report,'author_rejected','operation-one')['acceptances'][0]
    saved['authority']='author_revised'
    with repo.db.connection() as db:db.execute('UPDATE app_settings SET payload=? WHERE key=?',(json.dumps(saved),prefix(story.id)+'acceptance:'+saved['id']))
    assert repo.get_version(ref.id).stale


def test_operation_id_with_namespace_words_is_not_truncated(tmp_path):
    from storygen.review.store import publish_scene
    repo,story,first,second,ref,run,target=setup(tmp_path)
    publish_scene(repo,run.id,report_for(repo,run,target),'author_rejected','command:report:x')
    assert not repo.get_version(ref.id).stale
