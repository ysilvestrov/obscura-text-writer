from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.generation.dependencies import save_manual_prose
from tests.impact.test_runner import runner


def app_for(root):
    repo,story,first,second,ref,worker,run,calls=runner(root/'data')
    worker.cancel(run.id)
    app=create_app(AppSettings(data_dir=root/'data',env_file=root/'absent.env'))
    return app,story,first,second,ref


def test_impact_preview_never_dispatches_and_stale_plan_is_rejected(tmp_path):
    app,story,first,second,ref=app_for(tmp_path)
    client=TestClient(app,base_url="http://127.0.0.1")
    response=client.post(f'/api/stories/{story.id}/impact/preview')
    assert response.status_code==200
    preview=response.json();assert preview['ready'] and preview['calls']==2
    before=len(app.state.repo.list_attempts(story.id))
    save_manual_prose(app.state.repo,first.id,'Інші передумови.',app.state.repo.get_scene(first.id).revision)
    result=client.post(f'/api/stories/{story.id}/impact',json=dict(request_id='new',fingerprint=preview['plan']['fingerprint'],budget_limit_usd=None))
    assert result.status_code==409
    assert len(app.state.repo.list_attempts(story.id))==before


def test_impact_api_queues_one_run_and_returns_public_findings(tmp_path):
    app,story,first,second,ref=app_for(tmp_path);client=TestClient(app,base_url="http://127.0.0.1")
    preview=client.post(f'/api/stories/{story.id}/impact/preview').json()
    body=dict(request_id='api-impact',fingerprint=preview['plan']['fingerprint'],budget_limit_usd=None)
    first_response=client.post(f'/api/stories/{story.id}/impact',json=body)
    assert first_response.status_code==200
    duplicate=client.post(f'/api/stories/{story.id}/impact',json=body)
    assert duplicate.json()['id']==first_response.json()['id']
    state=client.get(f'/api/stories/{story.id}/impact').json()
    assert state['pending'] and not state['reports']


def test_chunk_preview_exposes_manifest_stamp_without_manuscript(tmp_path):
    from tests.impact.test_chunk_runner import chunk_runner
    repo,story,second,worker,run,calls,prepared=chunk_runner(tmp_path/'data')
    worker.cancel(run.id)
    app=create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'))
    client=TestClient(app,base_url='http://127.0.0.1')
    result=client.post(f'/api/stories/{story.id}/impact/preview')
    data=result.json();assert data['ready'] and data['protocol']==2
    assert data['calls']>2 and data['part_counts']['reduce_check']>0
    assert 'chunk_manifest' not in data
    assert data['plan']['fingerprint']==prepared['chunk_manifest']['fingerprint']
    assert 'documents' not in data['plan']
    assert not calls
