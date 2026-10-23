import json

from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.authoring.test_role_profiles import seeded


def test_role_horizons_and_shared_ending_roundtrip_without_leaking_into_bundle(tmp_path):
    repo,story,_=seeded(tmp_path)
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        base=f'/api/stories/{story.id}'
        initial=client.get(base+'/settings').json()
        writer=initial['roles']['writer'];writer.update(future_plan_mode='next_n',future_plan_count=2)
        response=client.put(base+'/settings',json={'expected_revision':initial['story']['revision'],'role':'writer','settings':writer})
        assert response.status_code==200,response.text
        updated=client.get(base+'/settings').json()
        assert updated['roles']['planner']['future_plan_mode']=='all'
        assert updated['roles']['writer']['future_plan_mode']=='next_n'
        profile=updated['profile'];profile['ending_goal']='АВТОРСЬКИЙ_ФІНАЛ'
        response=client.put(base+'/settings',json={'expected_revision':updated['story']['revision'],'profile':profile})
        assert response.status_code==200,response.text
        current=client.get(base+'/settings').json()
        assert current['profile']['ending_goal']=='АВТОРСЬКИЙ_ФІНАЛ'
        bundle=client.post(base+'/role-profiles/capture',json={'expected_revision':current['story']['revision'],'name':'З горизонтом'}).json()
        exported=client.get(f"/api/role-profiles/{bundle['id']}/versions/1/export")
        assert exported.status_code==200 and 'АВТОРСЬКИЙ_ФІНАЛ' not in exported.text
        document=json.loads(exported.content)
        assert document['roles']['writer']['settings']['future_plan_count']==2
        assert document['roles']['writer']['settings']['future_plan_mode']=='next_n'
        target=client.post('/api/stories',json={'title':'Новий твір'}).json()
        apply=client.post(f"/api/stories/{target['id']}/role-profiles/apply",json={'profile_id':bundle['id'],'version':1,'expected_revision':target['revision']})
        assert apply.status_code==200
        result=client.get(f"/api/stories/{target['id']}/settings").json()
        assert result['roles']['writer']['future_plan_mode']=='next_n' and result['profile']['ending_goal']==''
        page=client.get(f'/stories/{story.id}/settings').text
        assert 'name="ending_goal"' in page


def test_oversize_ending_and_invalid_horizon_are_rejected(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Ліміти'}).json()
        endpoint=f"/api/stories/{story['id']}/settings"
        for body in [{'profile':{'ending_goal':'x'*12001}}, {'role':'writer','settings':{'provider':{'model':'fake'},'future_plan_count':-1}}]:
            assert client.put(endpoint,json={'expected_revision':story['revision'],**body}).status_code==422
        assert client.get(endpoint).json()['story']['revision']==story['revision']
