from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app


def test_trash_restore_api_and_revision_guards(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        story=client.post('/api/stories',json={'title':'Твір'}).json()
        scene=client.post(f'/api/stories/{story["id"]}/scenes',json={'title':'Сцена'}).json()
        ref=app.state.repo.save_version(story['id'],scene['id'],'manual','Збережений текст',[])
        removed=client.post(f'/api/scenes/{scene["id"]}/trash',json={'story_id':story['id'],'expected_revision':scene['revision']})
        assert removed.status_code==200
        assert client.get(f'/api/stories/{story["id"]}').json()['scenes']==[]
        assert client.get(f'/api/versions/{ref.id}').status_code==404
        assert client.patch(f'/api/scenes/{scene["id"]}',json={'story_id':story['id'],'expected_revision':removed.json()['revision'],'beats':'Підміна'}).status_code==404
        assert client.get(f'/api/stories/{story["id"]}/trash').json()['scenes'][0]['id']==scene['id']
        assert client.post(f'/api/scenes/{scene["id"]}/restore',json={'story_id':story['id'],'expected_revision':scene['revision']}).status_code==409
        assert client.post(f'/api/scenes/{scene["id"]}/restore',json={'story_id':story['id'],'expected_revision':removed.json()['revision']}).status_code==200
        assert client.get(f'/api/versions/{ref.id}').json()['text']=='Збережений текст'
        story=client.get(f'/api/stories/{story["id"]}').json()['story']
        removed=client.post(f'/api/stories/{story["id"]}/trash',json={'expected_revision':story['revision']})
        assert removed.status_code==200
        assert client.get(f'/stories/{story["id"]}').status_code==404
        assert story['id'] not in client.get('/').text
        assert client.get('/api/trash').json()['stories'][0]['id']==story['id']
        assert client.post(f'/api/stories/{story["id"]}/restore',json={'expected_revision':removed.json()['revision']}).status_code==200
        assert client.get(f'/api/versions/{ref.id}').json()['text']=='Збережений текст'


def test_reorder_and_add_ignore_trashed_scenes(tmp_path):
    from storygen.authoring.trash import trash_scene, restore_scene
    from storygen.authoring.service import reorder_scenes
    from storygen.domain import StoryCreate, SceneCreate
    repo=create_app(AppSettings(data_dir=tmp_path)).state.repo
    story=repo.create_story(StoryCreate(title='Твір'))
    a,b,c=[repo.create_scene(story.id,SceneCreate(title=t)) for t in ['A','B','C']]
    removed=trash_scene(repo,story.id,b.id,0)
    reorder_scenes(repo,story.id,[c.id,a.id],repo.get_story(story.id).revision)
    d=repo.create_scene(story.id,SceneCreate(title='D'))
    assert [s.position for s in repo.list_scenes(story.id)]==[0,1,2]
    restore_scene(repo,story.id,b.id,repo.get_scene(b.id,include_trashed=True).revision)
    assert [s.id for s in repo.list_scenes(story.id)]==[c.id,b.id,a.id,d.id]


def test_trash_ui_preserves_unsaved_buffers():
    import shutil
    import subprocess
    from pathlib import Path
    import pytest
    node=shutil.which('node')
    if node is None:pytest.skip('Node required for browser module test')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/trash_regressions.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
