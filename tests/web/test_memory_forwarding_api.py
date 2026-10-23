from fastapi.testclient import TestClient
from storygen.web.app import create_app
from storygen.application.settings import AppSettings
from tests.memory.test_forwarding import seeded


def test_memory_table_http_choices_cas_and_unknown_scope(tmp_path):
    repo,_,scenes=seeded(tmp_path)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        url=f'/api/scenes/{scenes[1].id}/memory-view'
        view=client.get(url).json();claim=view['rows'][0]['claim_id']
        body={key:view[key] for key in ['expected_revision','fingerprint']};body['choices']={claim:False}
        response=client.put(url,json=body)
        assert response.status_code==200 and not response.json()['rows'][0]['forward']
        assert client.put(url,json=body).status_code==409
        latest=response.json();body={key:latest[key] for key in ['expected_revision','fingerprint']}
        assert client.put(url,json={**body,'choices':{'foreign':False}}).status_code==400
        assert client.put(url,json={**body,'choices':{claim:'false'}}).status_code==422
        assert client.get('/api/scenes/missing/memory-view').status_code==404
