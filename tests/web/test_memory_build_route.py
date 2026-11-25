"""R-48 PR 2 (design §5): `GET /api/stories/{id}/memory-build` — the scene the memory build starts from and its size."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from tests.generation.test_memory_build import give_memory, written_book


def test_memory_build_route_returns_target_and_count(tmp_path):
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.', 'Третя.'])
    give_memory(repo, story, scenes[0])
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.get(f'/api/stories/{story.id}/memory-build')
        assert response.status_code == 200
        assert response.json() == {'scene_id': scenes[1].id, 'count': 2, 'buildable': True}
        for scene in scenes[1:]:
            give_memory(app.state.repo, story, scene)
        assert client.get(f'/api/stories/{story.id}/memory-build').json() == {'scene_id': None, 'count': 0, 'buildable': False}
        assert client.get('/api/stories/missing/memory-build').status_code == 404


def test_memory_build_route_survives_unreadable_cards(tmp_path):
    # Review M-2: as readiness, an unreadable cards file gives no cast proposal, not a failed preview.
    from tests.generation.test_memory_build import with_cards
    repo, story, scenes = written_book(tmp_path, ['Оля йде.', 'Друга.'])
    story = with_cards(repo, story, 'Оля')
    give_memory(repo, story, scenes[0])
    cards = repo.get_version(story.characters_version_id)
    repo.files.resolve(cards.relative_path).write_bytes(b'broken')
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        response = client.get(f'/api/stories/{story.id}/memory-build')
        assert response.status_code == 200, response.text
        assert response.json() == {'scene_id': scenes[1].id, 'count': 1, 'buildable': True}


def test_two_confirmed_memory_builds_give_one_run_and_one_409(tmp_path):
    # Review I-1: two confirms of the same preview (a retried MCP call, a second tab) queue one paid run; the other is 409.
    repo, story, scenes = written_book(tmp_path, ['Перша.', 'Друга.'])
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        app.state.coordinator.stop()  # no worker: the first run stays queued, as one waiting behind another would
        preview = client.get(f'/api/stories/{story.id}/readiness',
                             params={'scene_id': scenes[0].id, 'operation': 'rebuild_memory'}).json()['operations']['rebuild_memory']
        request = {'story_id': story.id, 'scene_id': scenes[0].id, 'mode': 'rebuild_memory',
                   'memory_plan_fingerprint': preview['plan_fingerprint']}
        answers = [client.post('/api/runs', json={'request_id': name, 'request': request}) for name in ('one', 'two')]
        assert [answer.status_code for answer in answers] == [200, 409]
        assert answers[1].json()['detail'].startswith('Побудова пам’яті цього твору вже в черзі')
        assert len(client.get(f'/api/stories/{story.id}/runs').json()['runs']) == 1


def test_book_in_progress_is_not_buildable(tmp_path):
    # Owner, 25.11.2026 (review I-2): prose in scene 1 only and plans after it — the build would be refused, so the menu
    # item is hidden; once every scene from the target to the end has finished prose, it is shown.
    from storygen.generation.dependencies import save_manual_prose
    repo, story, scenes = written_book(tmp_path, ['Перша.', '', ''])
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        assert client.get(f'/api/stories/{story.id}/memory-build').json() == {'scene_id': scenes[0].id, 'count': 3,
                                                                              'buildable': False}
        for scene, text in zip(scenes[1:], ['Друга.', 'Третя.']):
            save_manual_prose(app.state.repo, scene.id, text, app.state.repo.get_scene(scene.id).revision)
        assert client.get(f'/api/stories/{story.id}/memory-build').json() == {'scene_id': scenes[0].id, 'count': 3,
                                                                              'buildable': True}


def test_memory_saved_from_the_chat_is_valid_for_the_build(tmp_path):
    # Review M-3, no loop on the chat path: memory saved through the chat stage result holds its link by construction, so
    # the build target moves past the scene.
    from tests.web.test_chat_stage_routes import MEMORY, app_with_scene, dump, save, task
    from storygen.generation.memory_build import memory_build_target
    app, repo, story, scene, client = app_with_scene(tmp_path)
    data = task(client, scene.id, 'memory')
    assert save(client, scene.id, 'memory', data['task_fingerprint'], dump(MEMORY)).status_code == 200
    view = repo.context_view(story.id)
    assert not view.is_stale(view.peek_scene(scene.id).heads['memory'])
    assert memory_build_target(view) == (None, 0)
