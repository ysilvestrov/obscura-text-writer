from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.review.test_runner import fixture


def test_review_commands_are_owned_cas_and_idempotent(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path/'data',concern=True)
    worker._execute(run.id)
    app=create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'))
    app.state.coordinator=worker
    client=TestClient(app,base_url='http://127.0.0.1')
    url=f'/api/stories/{story.id}/review/{run.id}'
    p=client.get(url).json();assert p['phase']=='awaiting_author'
    assert client.get(f'/api/stories/foreign/review/{run.id}').status_code==400
    body=dict(operation_id='api-choice',fingerprint=p['fingerprint'],choices={c['id']:'reject' for c in p['report']['concerns']})
    wrong={**body,'fingerprint':'0'*64}
    assert client.post(url+'/decide',json=wrong).status_code==409
    a=client.post(url+'/decide',json=body);assert a.status_code==200,a.text
    assert client.post(url+'/decide',json=body).json()==a.json()
    assert len(calls)==4


def test_review_preview_is_versioned_and_read_only(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path/'data')
    worker.cancel(run.id)
    app=create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'))
    client=TestClient(app,base_url='http://127.0.0.1')
    p=client.post(f'/api/stories/{story.id}/review/preview').json()
    assert p['ready'] and p['protocol']==3 and p['future_calls_unknown']
    assert 'registry' not in str(p)
    assert not calls
    response=client.post(f'/api/stories/{story.id}/review',json=dict(request_id='new-review',fingerprint=p['fingerprint']))
    assert response.status_code==200,response.text
    assert response.json()['impact']['protocol']==3
