"""MCP-BRIDGE package 6: start_run and get_run through the real Obscura app (S47–S50). No provider calls: the worker is not
started (the test client is not a context manager), and readiness is stubbed where a ready run is needed."""
import pytest

pytest.importorskip('mcp')

from storygen.domain import ContentRating, SceneCreate, StoryCreate  # noqa: E402
from storygen.generation import readiness  # noqa: E402
from storygen.mcp.bridge import BRIDGE_HEADERS, build_server  # noqa: E402
from storygen.web.bridge_marker import CHAT_WRITES, RUN_OWNER_ONLY  # noqa: E402

from tests.mcp.test_bridge import call, obscura, text  # noqa: E402
from tests.mcp.test_bridge_settings import ok  # noqa: E402

READY = {'ready': True, 'reason': None, 'roles': {'planner': {'provider': 'local', 'model': 'm'}}, 'calls': 1, 'warnings': []}


def setup(tmp_path, mode='obscura'):
    app, http = obscura(tmp_path)
    http.headers.update(BRIDGE_HEADERS)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк', writing_mode=mode, content_rating=ContentRating(sexual=0, violence=0, themes=0)))
    scene = repo.create_scene(story.id, SceneCreate(title='Туман', beats='Марта виявляє зламаний маяк.'))
    return app, repo, story, scene, build_server(http)


@pytest.fixture
def ready(monkeypatch):
    monkeypatch.setattr(readiness, 'preview', lambda *_args, **_kw: dict(READY))


@pytest.mark.req('MCP-BRIDGE')
def test_start_run_without_confirm_only_previews(tmp_path, ready):
    app, repo, story, scene, server = setup(tmp_path)
    data = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'brief', 'scene_id': scene.id}))
    assert data['started'] is False
    assert data['preview']['ready'] is True and data['preview']['calls'] == 1 and data['preview']['roles']
    assert set(data['preview']['budget']) == {'limit_usd', 'spent_usd', 'available_usd', 'default_run_limit_usd'}
    assert app.state.coordinator.list_runs() == []


@pytest.mark.req('MCP-BRIDGE')
def test_start_run_with_confirm_queues_a_marked_run(tmp_path, ready):
    app, repo, story, scene, server = setup(tmp_path)
    data = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'brief', 'scene_id': scene.id, 'confirm': True, 'budget_limit_usd': '0.50'}))
    assert data['started'] is True and data['state'] == 'queued'
    run = app.state.coordinator.get_run(data['run_id'])
    assert run.origin == 'mcp' and run.request.stage == 'brief' and run.request.budget_limit_usd == '0.50'
    state = ok(call(server, 'get_run', {'run_id': run.id}))
    assert state['state'] == 'queued' and state['action'] == 'brief' and state['attempts'] == []
    cancelled = ok(call(server, 'get_run', {'run_id': run.id, 'cancel': True}))
    assert cancelled['state'] == 'cancelled'


@pytest.mark.req('MCP-BRIDGE')
def test_unready_run_is_refused_with_reason(tmp_path):
    app, repo, story, scene, server = setup(tmp_path)
    preview = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'draft', 'scene_id': scene.id}))
    assert preview['preview']['ready'] is False and preview['preview']['reason']
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'draft', 'scene_id': scene.id, 'confirm': True})
    assert refused.is_error and preview['preview']['reason'] in text(refused)
    assert app.state.coordinator.list_runs() == []


@pytest.mark.req('MCP-BRIDGE')
def test_memory_needing_author_approval_is_refused_with_advice(tmp_path, monkeypatch):
    monkeypatch.setattr(readiness, 'preview', lambda *_a, **_k: {**READY, 'ready': False, 'can_confirm': True,
                                                                 'reason': 'Попередня пам’ять потребує авторського підтвердження'})
    app, repo, story, scene, server = setup(tmp_path)
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'memory', 'scene_id': scene.id, 'confirm': True})
    assert refused.is_error and 'Obscura' in text(refused) and 'підтверд' in text(refused)
    assert app.state.coordinator.list_runs() == []


@pytest.mark.req('MCP-BRIDGE')
def test_publication_suggestion_run_and_result(tmp_path, monkeypatch):
    from storygen.generation import publication_metadata
    monkeypatch.setattr(publication_metadata, 'readiness', lambda *_a, **_k: dict(READY))
    app, repo, story, scene, server = setup(tmp_path)
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'publication_suggest', 'scene_id': scene.id})
    assert refused.is_error and 'publication_suggest стосується твору' in text(refused)
    data = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'publication_suggest', 'confirm': True}))
    run = app.state.coordinator.get_run(data['run_id'])
    assert run.request.mode == 'publication_suggest' and run.origin == 'mcp'
    state = ok(call(server, 'get_run', {'run_id': run.id}))
    assert state['action'] == 'publication_suggest' and state['suggestions'] == {'proposals': [], 'history': []}


@pytest.mark.req('MCP-BRIDGE')
def test_chat_mode_and_unknown_action_are_refused(tmp_path, ready):
    app, repo, story, scene, server = setup(tmp_path, mode='chat')
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'brief', 'scene_id': scene.id})
    assert refused.is_error and CHAT_WRITES in text(refused)
    unknown = call(server, 'start_run', {'story_id': story.id, 'action': 'scene', 'scene_id': scene.id})
    assert unknown.is_error and 'brief, draft, edit, memory, publication_suggest' in text(unknown)
    assert app.state.coordinator.list_runs() == []


@pytest.mark.req('MCP-BRIDGE')
def test_get_run_cannot_cancel_authors_run(tmp_path, ready):
    from storygen.run_models import RunRequest
    app, repo, story, scene, server = setup(tmp_path)
    run = app.state.coordinator.enqueue(RunRequest(story_id=story.id, scene_id=scene.id, mode='stage', stage='brief'), 'ui')
    refused = call(server, 'get_run', {'run_id': run.id, 'cancel': True})
    assert refused.is_error and '403' in text(refused) and RUN_OWNER_ONLY in text(refused)
    assert app.state.coordinator.get_run(run.id).state == 'queued'
    assert ok(call(server, 'get_run', {'run_id': run.id}))['state'] == 'queued'


@pytest.mark.req('MCP-BRIDGE')
def test_next_steps_follow_the_story_mode(tmp_path):
    app, repo, story, scene, server = setup(tmp_path)
    assert 'start_run' in text(call(server, 'next_steps', {'scene_id': scene.id}))
    chat = setup(tmp_path / 'chat', mode='chat')
    steps = text(call(chat[4], 'next_steps', {'scene_id': chat[3].id}))
    assert 'get_stage_task' in steps and 'start_run' not in steps
