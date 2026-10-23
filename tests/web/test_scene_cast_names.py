import json
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.domain import StoryCreate,SceneCreate


def test_story_view_returns_name_registry_without_character_descriptions(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path));repo=app.state.repo
    story=repo.create_story(StoryCreate(title='Твір'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена',character_ids=['internal-a']))
    def publish(name):
        cards=[dict(schema_version=2,id='internal-a',name=name,entries=[dict(id='entry-a',text='ПРИВАТНИЙ ОПИС',availability='timeless',origin='author')])]
        ref=repo.save_version(story.id,None,'character_cards',json.dumps(cards,ensure_ascii=False),[])
        repo.publish_story_material(story.id,'characters_version_id',ref.id,repo.get_story(story.id).revision)
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/stories/'+story.id).json()['character_names']=={}
        publish('Олена')
        result=client.get('/api/stories/'+story.id).json()
        assert result['character_names']=={'internal-a':'Олена'}
        assert result['scenes'][0]['character_ids']==['internal-a']
        assert 'ПРИВАТНИЙ ОПИС' not in json.dumps(result,ensure_ascii=False)
        publish('ОЛЕНА')
        assert client.get('/api/stories/'+story.id).json()['character_names']=={'internal-a':'ОЛЕНА'}


def test_story_view_preserves_effective_review_status_after_dependency_return(tmp_path):
    from storygen.generation.context import build_context
    from storygen.providers.models import RoleSettings,ProviderSettings
    app=create_app(AppSettings(data_dir=tmp_path));repo=app.state.repo
    story=repo.create_story(StoryCreate(title='Актуальність'))
    scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    draft=repo.save_version(story.id,scene.id,'draft','A',[])
    scene=repo.set_head(scene.id,'draft',draft.id,scene.revision)
    context=build_context(repo,scene.id,'edit',RoleSettings(provider=ProviderSettings(model='fake'),edit_mode='patches'))
    prose=repo.save_version(story.id,scene.id,'edited','Результат',[draft.id],dependency_snapshot=context.dependency_snapshot)
    scene=repo.set_head(scene.id,'prose',prose.id,scene.revision)
    other=repo.save_version(story.id,scene.id,'draft','B',[])
    scene=repo.set_head(scene.id,'draft',other.id,scene.revision)
    assert repo.get_scene(scene.id).needs_review
    repo.set_head(scene.id,'draft',draft.id,scene.revision)
    assert not repo.get_scene(scene.id).needs_review
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        assert client.get('/api/stories/'+story.id).json()['scenes'][0]['needs_review'] is False
