from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def test_word_targets_above_recommendation_round_trip(tmp_path):
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        response=client.post('/api/stories',json={'title':'Довгий твір','target_words':25000})
        assert response.status_code==200,response.text
        story=response.json()
        scene=client.post(f"/api/stories/{story['id']}/scenes",json={'title':'Довга сцена','target_words':16000})
        assert scene.status_code==200,scene.text
        scene=scene.json()
        changed=client.patch(f"/api/scenes/{scene['id']}",json={'story_id':story['id'],'expected_revision':scene['revision'],'target_words':30000})
        assert changed.status_code==200,changed.text
        view=client.get(f"/api/stories/{story['id']}").json()
        assert view['story']['target_words']==25000
        assert view['scenes'][0]['target_words']==30000
        html=client.get('/').text
        assert 'max="15000"' not in html
        assert 'word_target.recommendation' in html
        assert client.post('/api/stories',json={'title':'Малий','target_words':4999}).status_code==422
