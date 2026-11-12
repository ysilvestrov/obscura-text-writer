"""MCP-BRIDGE package 6: runs requested by the bridge — mode, allowed run kinds, own-run cancel, origin (S49–S51). No provider calls:
the client is not started as a context manager, so the worker does not pick runs up, and readiness is stubbed."""
import pytest

from storygen.generation import readiness
from storygen.web.bridge_marker import CHAT_WRITES, RUN_OWNER_ONLY
from tests.web.test_chat_stage_routes import app_with_scene

BRIDGE = {'X-Obscura-Client': 'mcp'}
READY = {'ready': True, 'roles': {'planner': {'provider': 'local', 'model': 'm'}}, 'calls': 1, 'warnings': []}


@pytest.fixture
def ready(monkeypatch):
    monkeypatch.setattr(readiness, 'preview', lambda *_args, **_kw: dict(READY))


def scene_app(tmp_path, mode):
    app, repo, story, scene, client = app_with_scene(tmp_path, prose=True)
    story = repo.get_story(story.id)
    if mode != story.writing_mode:
        assert client.put(f'/api/stories/{story.id}/writing-mode', json={'writing_mode': mode, 'expected_revision': story.revision}).status_code == 200
    return app, repo, story, scene, client


def stage_run(client, story, scene, request_id='r1', headers=BRIDGE, **extra):
    request = {'story_id': story.id, 'scene_id': scene.id, 'mode': 'stage', 'stage': 'brief', **extra}
    return client.post('/api/runs', json={'request_id': request_id, 'request': request}, headers=headers)


@pytest.mark.req('MCP-BRIDGE')
def test_bridge_stage_run_in_obscura_mode_is_marked(tmp_path, ready):
    app, repo, story, scene, client = scene_app(tmp_path, 'obscura')
    response = stage_run(client, story, scene)
    assert response.status_code == 200, response.text
    run = app.state.coordinator.get_run(response.json()['id'])
    assert run.origin == 'mcp'
    again = stage_run(client, story, scene)
    assert again.json()['id'] == run.id and len(app.state.coordinator.list_runs()) == 1
    author = stage_run(client, story, scene, request_id='ui', headers={})
    assert app.state.coordinator.get_run(author.json()['id']).origin is None


@pytest.mark.req('MCP-BRIDGE')
def test_chat_mode_refuses_bridge_runs_but_not_the_author(tmp_path, ready):
    app, repo, story, scene, client = scene_app(tmp_path, 'chat')
    refused = stage_run(client, story, scene)
    assert refused.status_code == 409 and CHAT_WRITES in refused.text
    assert app.state.coordinator.list_runs() == []
    assert stage_run(client, story, scene, request_id='ui', headers={}).status_code == 200


@pytest.mark.req('MCP-BRIDGE')
def test_bridge_may_not_start_other_run_kinds(tmp_path, ready):
    app, repo, story, scene, client = scene_app(tmp_path, 'obscura')
    for request in ({'story_id': story.id, 'scene_id': scene.id, 'mode': 'scene'}, {'story_id': story.id, 'mode': 'prepare'},
                    {'story_id': story.id, 'scene_id': scene.id, 'mode': 'rebuild_memory'}):
        refused = client.post('/api/runs', json={'request_id': 'x-' + request['mode'], 'request': request}, headers=BRIDGE)
        assert refused.status_code == 403 and RUN_OWNER_ONLY in refused.text, request
    for path in (f'/api/stories/{story.id}/prepare', f'/api/stories/{story.id}/evaluate', f'/api/scenes/{scene.id}/rebuild-memory',
                 f'/api/scenes/{scene.id}/copyedits/a1/classify', f'/api/stories/{story.id}/impact', f'/api/stories/{story.id}/impact/preview',
                 f'/api/stories/{story.id}/review', f'/api/stories/{story.id}/review/r1/finish', '/api/runs/cancel-request'):
        response = client.post(path, json={'request_id': 'x'}, headers=BRIDGE)
        assert response.status_code == 403 and RUN_OWNER_ONLY in response.text, (path, response.status_code)
    assert app.state.coordinator.list_runs() == []


@pytest.mark.req('MCP-BRIDGE')
def test_bridge_cancels_only_its_own_run_and_never_pauses(tmp_path, ready):
    app, repo, story, scene, client = scene_app(tmp_path, 'obscura')
    own = stage_run(client, story, scene).json()['id']
    foreign = stage_run(client, story, scene, request_id='ui', headers={}).json()['id']
    for action in ('pause', 'resume'):
        refused = client.post(f'/api/runs/{own}/{action}', json={}, headers=BRIDGE)
        assert refused.status_code == 403, action
    refused = client.post(f'/api/runs/{own}/continue-after-acceptance', json={'version_id': 'v', 'expected_cursor': 0, 'expected_scene_revision': 0, 'acceptance_id': 'a'}, headers=BRIDGE)
    assert refused.status_code == 403
    refused = client.post(f'/api/runs/{foreign}/cancel', json={}, headers=BRIDGE)
    assert refused.status_code == 403 and RUN_OWNER_ONLY in refused.text
    assert app.state.coordinator.get_run(foreign).state == 'queued'
    cancelled = client.post(f'/api/runs/{own}/cancel', json={}, headers=BRIDGE)
    assert cancelled.status_code == 200 and cancelled.json()['state'] in {'cancelled', 'cancellation_requested'}


@pytest.mark.req('MCP-BRIDGE')
def test_run_refusals_are_translated(tmp_path, ready):
    app, repo, story, scene, client = scene_app(tmp_path, 'chat')
    refused = stage_run(client, story, scene, headers={**BRIDGE, 'Accept-Language': 'en'})
    assert refused.status_code == 409 and CHAT_WRITES not in refused.json()['detail']
    refused = client.post('/api/runs', json={'request_id': 'x', 'request': {'story_id': story.id, 'mode': 'prepare'}}, headers={**BRIDGE, 'Accept-Language': 'en'})
    assert refused.status_code == 403 and RUN_OWNER_ONLY not in refused.json()['detail']
