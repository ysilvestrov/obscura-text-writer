import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.run_models import RunRequest
from tests.generation.test_editor_loop import seeded,patch


def test_enqueue_idempotency_readiness_and_one_publication(tmp_path,monkeypatch):
    repo,scene,draft,worker,run,calls=seeded(tmp_path,[patch('йшов','йшла'),'{"edits":[]}'])
    app=create_app(AppSettings(data_dir=tmp_path));app.state.coordinator=worker
    monkeypatch.setattr(worker,'start',lambda:None)
    monkeypatch.setattr(worker,'stop',lambda:None)
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        p=client.get(f'/api/stories/{scene.story_id}/readiness?scene_id={scene.id}').json()['operations']['edit_loop']
        assert p['ready'] and p['calls']==5 and list(p['roles'])==['editor']
        assert client.post('/api/runs',json={'request_id':'loop','request':run.request.model_dump()}).json()['id']==run.id
        assert not calls
        result=client.post('/api/runs',json={'request_id':'duplicate','request':run.request.model_dump()})
        assert result.status_code==400
        worker._execute(run.id)
        run=worker.get_run(run.id);id=run.editor_loop['proposal_attempt_id']
        url=f'/api/scenes/{scene.id}/copyedits/{id}'
        preview=client.get(url).json()
        result=client.post(url,json=dict(expected_revision=preview['expected_revision'],proposal_fingerprint=preview['proposal_fingerprint'],selected_indices=[0]))
        assert result.status_code==200 and result.json()['run']['state']=='completed'
        assert len(calls)==2 and repo.get_scene(scene.id).heads['draft']==draft.id


def test_readiness_is_read_only_and_supports_no_draft_if_prose_selected(tmp_path):
    repo,scene,_,worker,run,_=seeded(tmp_path,['{"edits":[]}'])
    before=len(repo.list_versions(scene.story_id,scene.id))
    assert worker.readiness(scene.story_id,scene.id)['operations']['edit_loop']['ready']
    assert len(repo.list_versions(scene.story_id,scene.id))==before
    prose=repo.save_version(scene.story_id,scene.id,'manual','Авторська проза.',[])
    repo.set_head(scene.id,'prose',prose.id,repo.get_scene(scene.id).revision)
    with repo.db.connection() as db:
        current=repo.get_scene(scene.id);current.heads.pop('draft');repo._save_scene(db,current)
    assert worker.readiness(scene.story_id,scene.id)['operations']['edit_loop']['ready']
    worker._execute(run.id)
    assert worker.get_run(run.id).state=='completed'
