import json

from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.authoring.test_role_profiles import seeded


def test_profile_http_roundtrip_and_conflict(tmp_path):
    repo,story,_=seeded(tmp_path)
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        captured=client.post(f'/api/stories/{story.id}/role-profiles/capture',json={'name':'Переносимий','expected_revision':story.revision})
        assert captured.status_code==200,captured.text
        saved=captured.json()
        listed=client.get('/api/role-profiles').json()
        assert listed['profiles'][0]['id']==saved['id']
        exported=client.get(f"/api/role-profiles/{saved['id']}/versions/1/export")
        assert 'attachment' in exported.headers['content-disposition']
        imported=client.post('/api/role-profiles/import',content=exported.content,headers={'content-type':'application/json'})
        assert imported.status_code==200 and imported.json()['id']!=saved['id']
        target=client.post('/api/stories',json={'title':'Новий'}).json()
        body={'profile_id':saved['id'],'version':1,'expected_revision':target['revision']}
        base=f"/api/stories/{target['id']}/role-profiles"
        assert client.post(base+'/preview',json=body).json()['roles']['writer']['provider']['model']=='local-test'
        assert client.post(base+'/apply',json=body).status_code==200
        assert client.post(base+'/apply',json=body).status_code==409
        page=client.get(f"/stories/{target['id']}/settings")
        assert 'role-profiles.js' in page.text
        settings=client.get(f"/api/stories/{target['id']}/settings").json()
        assert set(settings['roles'])=={'planner','writer','editor','memory'}


def test_import_rejects_secret_without_echo_and_has_size_limit(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        raw=json.dumps({'api_key':'private-value'})
        response=client.post('/api/role-profiles/import',content=raw)
        assert response.status_code==400 and 'private-value' not in response.text
        response=client.post('/api/role-profiles/import',content='x'*(2*1024*1024+1))
        assert response.status_code==413
        assert client.get('/api/role-profiles').json()['profiles']==[]
