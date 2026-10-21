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
    repo=app.state.repo;story=repo.create_story(StoryCreate(title='Веб'));scene=repo.create_scene(story.id,SceneCreate(title='Сцена',beats='Ранок у бібліотеки'))
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


def test_partial_reload_tolerates_incomplete_utf8_tail_during_append(tmp_path):
    from storygen.domain import StageAttempt
    from storygen.generation.worker import RunRequest
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Потік'))
    scene = repo.create_scene(story.id, SceneCreate(title='Ранок', beats='Ранок'))
    save_role_settings(repo, story.id, 'planner', RoleSettings(provider=ProviderSettings(model='offline')), repo.get_story(story.id).revision)
    run = app.state.coordinator.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'utf8')
    attempt = StageAttempt(id='utf8-attempt', run_id=run.id, story_id=story.id, scene_id=scene.id, stage='brief', context={}, partial_path='partial.txt')
    repo.save_attempt(attempt)
    repo.files.write('partial.txt', 'Текст '.encode('utf-8') + b'\xd1')
    # No lifespan/worker: model calls are unnecessary to exercise the reload API.
    client = TestClient(app, base_url='http://127.0.0.1:8765')
    response = client.get(f'/api/runs/{run.id}')
    assert response.status_code == 200 and response.json()['partial'] == 'Текст '
    repo.files.write('partial.txt', 'Текст ї'.encode('utf-8'))
    assert client.get(f'/api/runs/{run.id}').json()['partial'] == 'Текст ї'


def test_batched_sse_replay_respects_both_cursors(tmp_path):
    import json
    from storygen.generation.worker import RunRequest
    from storygen.generation.stream_buffer import StreamBuffer
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Replay'))
    scene = repo.create_scene(story.id, SceneCreate(title='Ранок', beats='Ранок'))
    save_role_settings(repo, story.id, 'planner', RoleSettings(provider=ProviderSettings(model='offline')), repo.get_story(story.id).revision)
    worker = app.state.coordinator
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'replay')
    def checkpoint(text):
        worker.event(run.id, 'delta', {'text': text})
    with StreamBuffer(repo.files.open_partial('partial.txt'), checkpoint, clock=lambda: 0) as buffer:
        for text in ['Перша ', 'частина']:
            buffer.append(text)
        buffer.flush()
        buffer.append(' — друга частина')
    client = TestClient(app, base_url='http://127.0.0.1:8765')
    def replay(after, header):
        response = client.get(f'/api/runs/{run.id}/events?once=true&after={after}', headers={'Last-Event-ID': str(header)})
        assert response.status_code == 200
        return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    first = replay(0, 1)
    assert [e['data']['text'] for e in first] == ['Перша частина', ' — друга частина']
    assert [e['seq'] for e in first] == [2, 3]
    assert replay(2, 1) == first[1:]
    assert replay(1, 2) == first[1:]
    assert replay(0, 3) == []
