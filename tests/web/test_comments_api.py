from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.domain import StoryCreate,SceneCreate
from tests.storage.test_comments import payload


def test_comments_atomic_api_and_legacy_save_source_mismatch(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'))
    repo=app.state.repo;story=repo.create_story(StoryCreate(title='Зорі'))
    scene=repo.create_scene(story.id,SceneCreate(title='Парк'))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        first=client.post(f'/api/scenes/{scene.id}/draft',json={'text':'😀 Лєра дивилася вгору.','expected_revision':scene.revision}).json()
        url=f'/api/scenes/{scene.id}/comments'
        assert client.get(url).json()['comment_set'] is None
        request={'text':'😀 Лєра дивилася вгору.','expected_revision':first['scene']['revision'],
                 'expected_comments_revision':0,'expected_source_version_id':first['version']['id'],
                 'comment_set':payload().model_dump(mode='json')}
        result=client.post(f'/api/scenes/{scene.id}/draft',json=request)
        assert result.status_code==200,result.text
        assert result.json()['version']['id']==first['version']['id']
        loaded=client.get(url).json()
        assert loaded['source_matches_current'] and loaded['expected_comments_revision']==1
        assert client.post(f'/api/scenes/{scene.id}/draft',json=request).status_code==409
        updated=client.post(f'/api/scenes/{scene.id}/draft',json={'text':'Інша чернетка.','expected_revision':first['scene']['revision']})
        assert updated.status_code==200
        assert not client.get(url).json()['source_matches_current']
        assert client.get(url).json()['comment_set']['id']==loaded['comment_set']['id']
        assert client.get(url+'?material=prose').status_code==422


def test_comments_require_explicit_source_and_revision(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path/'data',env_file=tmp_path/'absent.env'))
    repo=app.state.repo;story=repo.create_story(StoryCreate(title='Зорі'));scene=repo.create_scene(story.id,SceneCreate(title='Парк'))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        result=client.post(f'/api/scenes/{scene.id}/draft',json={'text':'Текст','expected_revision':scene.revision,'comment_set':{'general':'Скоротити'}})
        assert result.status_code==422
        assert not repo.get_scene(scene.id).heads
