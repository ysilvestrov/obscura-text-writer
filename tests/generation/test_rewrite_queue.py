from storygen.generation.worker import RunCoordinator
from test_assisted_writing import Gateway

def test_rewrite_queue_one_call_idempotent_and_draft_unchanged(rewrite_case):
    repo,scene,source,notes,role,request=rewrite_case
    gateway=Gateway('Вечір був тихим. Вона поспішала додому.')
    worker=RunCoordinator(repo,gateway_factory=lambda _:gateway)
    run=worker.enqueue(request,'rewrite-one')
    assert worker.enqueue(request,'rewrite-one').id==run.id
    assert run.tasks==[{'scene_id':scene.id,'stage':'rewrite'}]
    run.state='running';repo.save_run(run);worker._execute(run.id)
    assert repo.get_run(run.id).state=='needs_review' and gateway.calls==1
    assert repo.get_scene(scene.id).heads['draft']==source.id
    assert [e.type for e in worker.list_events(run.id)].count('stage_started')==1


def test_review_cannot_resume_into_another_call(rewrite_case):
    import pytest
    repo,scene,source,notes,role,request=rewrite_case
    gateway=Gateway('Вечір був тихим. Вона поспішала додому.')
    worker=RunCoordinator(repo,gateway_factory=lambda _:gateway)
    run=worker.enqueue(request,'rewrite-review');run.state='running';repo.save_run(run);worker._execute(run.id)
    with pytest.raises(ValueError,match='перегля'):worker.resume(run.id)
    assert gateway.calls==1
