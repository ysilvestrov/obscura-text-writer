"""CHARACTER-EXTRACT (R-51 PR 1): the MCP bridge — start_run(action='character_extract'), the result in get_run and
accept_character_proposal, through the real Obscura app. The search writes no text of the book, so both writing modes may use it."""
import pytest

pytest.importorskip('mcp')

import anyio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from mcp import Client  # noqa: E402

from storygen.application.settings import AppSettings  # noqa: E402
from storygen.mcp.bridge import BRIDGE_HEADERS, EXTRACT_FINGERPRINT, EXTRACT_PLAN_STALE, TOOLS, build_server  # noqa: E402
from storygen.web.app import create_app  # noqa: E402

from tests.characters.test_extract_accept import book, cast, finished_run, new_card, quote  # noqa: E402
from tests.mcp.test_bridge import call, text  # noqa: E402
from tests.mcp.test_bridge_manuscript import author_mode  # noqa: E402
from tests.mcp.test_bridge_settings import ok  # noqa: E402


def bridge(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    http = TestClient(app, base_url='http://127.0.0.1:8765')
    http.headers.update(BRIDGE_HEADERS)
    return app, http, build_server(http)


def setup(tmp_path, mode='chat'):
    repo, story, scenes = book(tmp_path)
    app, http, server = bridge(tmp_path)
    if mode != story.writing_mode:
        author_mode(app, story, mode)
    return app, http, server, story, scenes


def runs(app):
    return app.state.coordinator.list_runs()


def preview(server, story, **extra):
    return ok(call(server, 'start_run', {'story_id': story.id, 'action': 'character_extract', **extra}))


@pytest.mark.req('CHARACTER-EXTRACT')
def test_start_run_preview_then_confirm(tmp_path):
    app, http, server, story, scenes = setup(tmp_path, 'obscura')
    data = preview(server, story, group_words=1000)
    assert data['started'] is False and runs(app) == []
    shown = data['preview']
    assert shown['ready'] is True, shown['reason']
    assert shown['scenes_count'] == 3 and shown['calls_bound'] >= 1 and shown['groups_count'] >= 1
    assert len(shown['plan_fingerprint']) == 64
    assert {'cost', 'cards_count', 'has_protagonist', 'pending_proposal', 'skipped', 'budget', 'roles', 'warnings'} <= set(shown)
    started = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'character_extract', 'confirm': True, 'group_words': 1000,
                                            'plan_fingerprint': shown['plan_fingerprint'], 'budget_limit_usd': '0.50'}))
    assert started['started'] is True and started['state'] == 'queued'
    run = app.state.coordinator.get_run(started['run_id'])
    assert run.origin == 'mcp' and run.request.mode == 'character_extract' and run.request.scene_id is None
    assert run.request.group_words == 1000 and run.request.extract_plan_fingerprint == shown['plan_fingerprint']
    assert run.request.budget_limit_usd == '0.50'
    assert ok(call(server, 'get_run', {'run_id': run.id}))['action'] == 'character_extract'


@pytest.mark.req('CHARACTER-EXTRACT')
def test_confirm_without_fingerprint_refused(tmp_path):
    app, http, server, story, scenes = setup(tmp_path)
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'character_extract', 'confirm': True})
    assert refused.is_error and EXTRACT_FINGERPRINT in text(refused)
    stale = call(server, 'start_run', {'story_id': story.id, 'action': 'character_extract', 'confirm': True, 'plan_fingerprint': 'a' * 64})
    assert stale.is_error and EXTRACT_PLAN_STALE in text(stale)
    assert runs(app) == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_scene_id_is_refused(tmp_path):
    app, http, server, story, scenes = setup(tmp_path)
    refused = call(server, 'start_run', {'story_id': story.id, 'action': 'character_extract', 'scene_id': scenes[0].id})
    assert refused.is_error and 'scene_id' in text(refused)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_chat_mode_story_allowed(tmp_path):
    app, http, server, story, scenes = setup(tmp_path, 'chat')
    assert app.state.repo.get_story(story.id).writing_mode == 'chat'
    shown = preview(server, story)['preview']
    assert shown['ready'] is True, shown['reason']
    started = ok(call(server, 'start_run', {'story_id': story.id, 'action': 'character_extract', 'confirm': True,
                                            'plan_fingerprint': shown['plan_fingerprint']}))
    assert started['started'] is True and len(runs(app)) == 1


@pytest.mark.req('CHARACTER-EXTRACT')
def test_server_guard_requires_the_fingerprint_from_the_bridge(tmp_path):
    app, http, server, story, scenes = setup(tmp_path, 'chat')
    body = {'request_id': 'mcp-x', 'request': {'story_id': story.id, 'mode': 'character_extract'}}
    refused = http.post('/api/runs', json=body)
    assert refused.status_code == 409 and runs(app) == []
    author = TestClient(app, base_url='http://127.0.0.1:8765').post('/api/runs', json={**body, 'request_id': 'own-x'})
    assert author.status_code == 200, author.text


@pytest.mark.req('CHARACTER-EXTRACT')
def test_get_run_reports_proposal(tmp_path):
    app, http, server, story, scenes = setup(tmp_path)
    s1 = scenes[0]
    run = finished_run(app.state.repo, story, scenes, cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))], casts=[cast(s1, 'new1')])
    data = ok(call(server, 'get_run', {'run_id': run.id}))
    block = data['character_extract']
    assert data['action'] == 'character_extract' and block['phase'] == 'done'
    assert block['proposal']['fingerprint'] == run.checkpoint['proposal']['fingerprint']
    assert [card['key'] for card in block['proposal']['cards']] == ['new1']
    older = finished_run(app.state.repo, story, scenes, request_id='extract-2')
    assert ok(call(server, 'get_run', {'run_id': run.id}))['character_extract']['proposal'] is None
    assert ok(call(server, 'get_run', {'run_id': older.id}))['character_extract']['proposal']['fingerprint']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_accept_tool_preview_then_confirm(tmp_path):
    app, http, server, story, scenes = setup(tmp_path)
    s1 = scenes[0]
    run = finished_run(app.state.repo, story, scenes, cards=[new_card('new1', 'Оля', quote(s1, 'Оля пішла додому'))], casts=[cast(s1, 'new1')])
    fingerprint = run.checkpoint['proposal']['fingerprint']
    arguments = {'story_id': story.id, 'run_id': run.id, 'fingerprint': fingerprint, 'cards': [{'key': 'new1', 'names': []}],
                 'casts': [s1.id]}
    before = app.state.repo.get_scene(s1.id).character_ids
    shown = ok(call(server, 'accept_character_proposal', arguments))
    assert shown['accepted'] is False and shown['preview']['applied']
    assert app.state.repo.get_scene(s1.id).character_ids == before
    done = ok(call(server, 'accept_character_proposal', {**arguments, 'confirm': True}))
    assert done['accepted'] is True and done['result']['applied'] and done['result']['changed_scene_ids'] == [s1.id]
    assert app.state.repo.get_scene(s1.id).character_ids != before
    again = call(server, 'accept_character_proposal', {**arguments, 'confirm': True})
    assert again.is_error


@pytest.mark.req('CHARACTER-EXTRACT')
def test_accept_tool_wrong_fingerprint_is_refused(tmp_path):
    app, http, server, story, scenes = setup(tmp_path)
    run = finished_run(app.state.repo, story, scenes)
    refused = call(server, 'accept_character_proposal', {'story_id': story.id, 'run_id': run.id, 'fingerprint': 'x', 'confirm': True})
    assert refused.is_error


@pytest.mark.req('CHARACTER-EXTRACT')
def test_tools_list_includes_accept_character_proposal(tmp_path):
    app, http, server = bridge(tmp_path)

    async def listing():
        async with Client(server) as client:
            return {tool.name: tool for tool in (await client.list_tools()).tools}
    tools = anyio.run(listing)
    assert len(TOOLS) == 30 and 'accept_character_proposal' in TOOLS and 'accept_character_proposal' in tools
    assert {'run_id', 'fingerprint', 'cards', 'name_updates', 'protagonist', 'casts', 'confirm'} <= set(
        tools['accept_character_proposal'].input_schema['properties'])
