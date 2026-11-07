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


def test_memory_view_rows_carry_supporting_quotes(tmp_path):
    import json
    from storygen.domain import StoryCreate,SceneCreate
    from storygen.storage.repository import Repository
    from storygen.generation.dependencies import save_manual_prose
    from storygen.memory.service import save_scene_memory
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Докази'))
    scene=repo.create_scene(story.id,SceneCreate(title='С1'))
    q1,q2,q3='Перша цитата.','Друга цитата.','Третя цитата.'
    save_manual_prose(repo,scene.id,f'{q1} {q2} {q3}',scene.revision)
    scene=repo.get_scene(scene.id);prose=scene.heads['prose']
    def ev(i,text,**kw):
        return dict(event_id=f'e{i}',claim_id=f'c{i}',operation='add',category='facts',text=text,source_version_id=prose,quote=q1,**kw)
    journal=dict(schema_version=2,source_prose_ids=[prose],events=[ev(1,'З доказами',supporting_quotes=[q2,q3]),ev(2,'Без доказів')])
    save_scene_memory(repo,scene.id,json.dumps(journal),scene.revision)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url='http://127.0.0.1:8765') as client:
        rows={r['text']:r for r in client.get(f'/api/scenes/{scene.id}/memory-view').json()['rows']}
    assert rows['З доказами']['supporting_quotes']==[q2,q3]
    assert rows['Без доказів']['supporting_quotes']==[]
