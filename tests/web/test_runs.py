import threading
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.domain import StoryCreate, SceneCreate
from storygen.authoring.blueprints import save_role_settings
from storygen.providers.models import RoleSettings, ProviderSettings
from storygen.providers.streaming import GenerationEvent


def test_run_returns_id_without_waiting_for_model(tmp_path):
    entered=threading.Event();release=threading.Event()
    class Gateway:
        def stream(self,context,cancel):
            entered.set();release.wait(3)
            yield GenerationEvent(type='cancelled')
    app=create_app(AppSettings(data_dir=tmp_path),gateway_factory=lambda _:Gateway())
    repo=app.state.repo;story=repo.create_story(StoryCreate(title='Веб'));scene=repo.create_scene(story.id,SceneCreate(title='Сцена',beats='Ранок у студії'))
    save_role_settings(repo,story.id,'planner',RoleSettings(provider=ProviderSettings(model='actual-id')),repo.get_story(story.id).revision)
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        response=client.post('/api/runs',json={'request_id':'web','request':{'story_id':story.id,'scene_id':scene.id,'mode':'stage','stage':'brief'}})
        assert response.status_code==200 and response.json()['id']
        assert entered.wait(2)
        run_id=response.json()['id']
        events=app.state.coordinator.list_events(run_id)
        replay=client.get(f'/api/runs/{run_id}/events?once=true',headers={'Last-Event-ID':str(events[0].seq)}).text
        assert 'id: 1\n' not in replay and 'stage_started' in replay
        assert app.state.coordinator.get_run(run_id).state=='running'
        client.post(f'/api/runs/{run_id}/cancel',json={})
        assert client.get(f'/api/runs/{run_id}').json()['run']['state']=='cancellation_requested'
        release.set()


def test_readiness_and_queue_share_prerequisite_reasons(tmp_path):
    app=create_app(AppSettings(data_dir=tmp_path))
    repo=app.state.repo;story=repo.create_story(StoryCreate(title='Передумови'));scene=repo.create_scene(story.id,SceneCreate(title='Сцена'))
    save_role_settings(repo,story.id,'writer',RoleSettings(provider=ProviderSettings(model='writer-only')),repo.get_story(story.id).revision)
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        preview=client.get(f'/api/stories/{story.id}/readiness?scene_id={scene.id}')
        assert preview.status_code==200
        draft=preview.json()['operations']['draft']
        assert not draft['ready'] and list(draft['roles'])==['writer']
        response=client.post('/api/runs',json={'request_id':'reject','request':{'story_id':story.id,'scene_id':scene.id,'mode':'stage','stage':'draft'}})
        assert response.status_code==400 and draft['reason'] in response.json()['detail']
        assert app.state.coordinator.list_runs()==[]
