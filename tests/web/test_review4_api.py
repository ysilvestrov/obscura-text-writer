from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.review.test_runner import fixture
from tests.review.test_authority4 import sources


def test_capability_preview_and_scoped_priority_round_trip(tmp_path):
    repo,story,first,second,ref,worker,run,calls=fixture(tmp_path/'data')
    worker.cancel(run.id)
    from tests.review.counter4 import activate_counter4
    activate_counter4(repo,second.id)
    app=create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'));app.state.coordinator=worker
    client=TestClient(app,base_url='http://127.0.0.1')
    base=f'/api/stories/{story.id}'
    data=client.get(base+'/impact').json()
    assert data.get('review_contract_versions')==[3,4]
    old=client.post(base+'/review/preview').json();assert old['contract_version']==3
    new=client.post(base+'/review/preview',json={'review_contract_version':4}).json()
    assert new['ready'] and new['contract_version']==4 and new['fingerprint']!=old['fingerprint']
    assert new['part_counts']['premise']>0 and not calls
    assert client.post(base+'/review/preview',json={'review_contract_version':5}).status_code==422
    preferred,superseded=sources(repo,second.id)
    url=base+f'/review/priorities/{second.id}'
    response=client.post(url,json=dict(material='prose',expected_revision=0,operation_id='api-priority',preferred=preferred,superseded=superseded))
    assert response.status_code==200,response.text
    policy=client.get(url).json();assert policy['authority_revisions']['prose']==1
    assert client.get(f'/api/stories/foreign/review/priorities/{second.id}').status_code==404
    assert not client.post(base+'/review/preview').json()['ready']
    assert not calls
