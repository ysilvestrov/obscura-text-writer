from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def test_writing_target_and_profile_are_atomic_and_noop_preserves_style(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Твір'}).json();id=story['id'];url=f'/api/stories/{id}/settings'
        scene=client.post(f'/api/stories/{id}/scenes',json={'title':'Сцена'}).json()
        loaded=client.get(url).json()
        response=client.put(url,json={'expected_revision':loaded['story']['revision'],'profile':loaded['profile'],'target_words':25000})
        assert response.status_code==200,response.text
        saved=response.json()
        assert saved['target_words']==25000 and saved['style_version_id'] is None
        assert app.state.repo.get_scene(scene['id']).target_words==1000
        profile={**loaded['profile'],'tone':'Спокійний'}
        conflict=client.put(url,json={'expected_revision':loaded['story']['revision'],'profile':profile,'target_words':30000})
        assert conflict.status_code==409
        assert app.state.repo.get_story(id).target_words==25000
        assert app.state.repo.get_story(id).style_version_id is None
        changed=client.put(url,json={'expected_revision':saved['revision'],'profile':profile,'target_words':30000})
        assert changed.status_code==200
        old_head=changed.json()['style_version_id']
        again=client.put(url,json={'expected_revision':changed.json()['revision'],'profile':profile})
        assert again.status_code==200 and again.json()['style_version_id']==old_head
        assert again.json()['target_words']==30000
        bad=client.put(url,json={'expected_revision':again.json()['revision'],'role':'writer','target_words':20000})
        assert bad.status_code==400
        shared=client.put(url+'/shared-provider',json={'expected_revision':again.json()['revision'],'provider':{'model':'x'},'target_words':20000})
        assert shared.status_code in {400,422}
