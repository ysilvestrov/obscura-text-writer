from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.domain import StoryCreate, SceneCreate


def test_versions_and_manual_edit_conflict_preserve_both_texts(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path));repo=app.state.repo
    story=repo.create_story(StoryCreate(title='Версії'));scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        first=client.post(f'/api/scenes/{scene.id}/prose',json={'text':'<script>авторський текст</script>','expected_revision':0})
        assert first.status_code==200
        assert client.post(f'/api/scenes/{scene.id}/prose',json={'text':'Незбережена нова правка','expected_revision':0}).status_code==409
        versions=client.get(f'/api/scenes/{scene.id}/versions').json()['versions']
        assert len(versions)==2
        assert repo.read_text(repo.get_scene(scene.id).heads['prose'])=='<script>авторський текст</script>'
        diff=client.get('/api/versions/compare',params={'left':versions[0]['id'],'right':versions[1]['id']}).json()
        assert 'Незбережена нова правка' in diff['right']
