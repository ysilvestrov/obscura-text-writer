from pathlib import Path

from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def test_browser_flow_create_import_edit(tmp_path):
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url="http://127.0.0.1:8765") as client:
        story=client.post('/api/stories',json={'title':'Двері'}).json()
        upload=client.post(f'/api/stories/{story["id"]}/sources',files={'plan':('plan.md',Path('tests/fixtures/prototype/plan.md').read_bytes(),'text/plain')})
        assert upload.status_code==200
        view=client.get(f'/api/stories/{story["id"]}').json()
        assert len(view['scenes'])==7
        scene=view['scenes'][0]
        reply=client.patch(f'/api/scenes/{scene["id"]}',json={'story_id':story['id'],'expected_revision':scene['revision'],'beats':'Змінений план'})
        assert reply.status_code==200
        assert client.get(f'/api/stories/{story["id"]}').json()['scenes'][0]['beats']=='Змінений план'
        assert client.patch(f'/api/scenes/{scene["id"]}',json={'story_id':story['id'],'expected_revision':scene['revision'],'beats':'Стара правка'}).status_code==409


def test_html_in_source_is_displayed_as_text(tmp_path):
    with TestClient(create_app(AppSettings(data_dir=tmp_path)),base_url="http://127.0.0.1:8765") as client:
        story=client.post('/api/stories',json={'title':'<script>alert(1)</script>'}).json()
        html=client.get(f'/stories/{story["id"]}').text
        assert '<script>alert(1)</script>' not in html
        assert '&lt;script&gt;' in html
        assert client.post('/api/stories',json={'title':'Чужий сайт'},headers={'origin':'https://other.example'}).status_code==403


def test_foreign_story_scene_is_rejected(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    from storygen.domain import StoryCreate,SceneCreate
    a=app.state.repo.create_story(StoryCreate(title='Один'))
    b=app.state.repo.create_story(StoryCreate(title='Два'))
    scene=app.state.repo.create_scene(b.id,SceneCreate(title='Чужа'))
    with TestClient(app,base_url="http://127.0.0.1:8765") as client:
        response=client.patch(f'/api/scenes/{scene.id}',json={'story_id':a.id,'expected_revision':0,'beats':'Підміна'})
        assert response.status_code==400
