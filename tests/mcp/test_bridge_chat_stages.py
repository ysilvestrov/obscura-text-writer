"""MCP-BRIDGE package 3: stage tasks and results from the chat through the real Obscura app (S41, S46)."""
import json

import pytest

pytest.importorskip('mcp')

from storygen.domain import ContentRating, SceneCreate, StoryCreate  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402

from tests.mcp.test_bridge import call, obscura, text  # noqa: E402
from tests.mcp.test_bridge_settings import ok, spy_writes  # noqa: E402
from tests.web.test_chat_stage_routes import MEMORY, PROSE  # noqa: E402


def scene_with_prose(tmp_path, prose=True):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк', content_rating=ContentRating(sexual=0, violence=0, themes=0)))
    scene = repo.create_scene(story.id, SceneCreate(title='Туман', beats='Марта виявляє зламаний маяк.', character_ids=['marta']))
    if prose:
        version = repo.save_version(story.id, scene.id, 'manual', PROSE, [])
        repo.set_head(scene.id, 'prose', version.id, repo.get_scene(scene.id).revision)
    return app, http, repo, story, repo.get_scene(scene.id)


@pytest.mark.req('MCP-BRIDGE')
def test_unknown_stage_is_refused_without_request(tmp_path):
    app, http, repo, story, scene = scene_with_prose(tmp_path)
    requests = []
    original = http.request
    http.request = lambda method, url, **kwargs: requests.append(url) or original(method, url, **kwargs)
    server = build_server(http)
    for tool, arguments in (('get_stage_task', {'scene_id': scene.id, 'stage': 'draft'}),
                            ('save_stage_result', {'scene_id': scene.id, 'stage': 'prepare', 'task_fingerprint': 'a' * 64, 'result': '{}'})):
        result = call(server, tool, arguments)
        assert result.is_error and 'brief, edit, memory' in text(result)
    assert requests == []


@pytest.mark.req('MCP-BRIDGE')
def test_memory_round_trip_through_bridge(tmp_path):
    """MCP-BRIDGE-S41: the result goes as an object; the origin is the MCP client."""
    app, http, repo, story, scene = scene_with_prose(tmp_path)
    server = build_server(http, client_name='Claude Desktop')
    task = ok(call(server, 'get_stage_task', {'scene_id': scene.id, 'stage': 'memory'}))
    assert task['instructions'] and '[f000001]' in task['material'] and task['result_format'] == 'json'
    saved = ok(call(server, 'save_stage_result', {'scene_id': scene.id, 'stage': 'memory', 'task_fingerprint': task['task_fingerprint'],
                                                  'result': MEMORY, 'model': 'test-model'}))
    assert saved['state'] == 'completed' and repo.get_scene(scene.id).heads['memory'] == saved['version_id']
    origin = repo.get_version(saved['version_id']).external_origin
    assert (origin.client, origin.model) == ('Claude Desktop', 'test-model')


@pytest.mark.req('MCP-BRIDGE')
def test_violations_reach_the_chat(tmp_path):
    app, http, repo, story, scene = scene_with_prose(tmp_path)
    server = build_server(http)
    task = ok(call(server, 'get_stage_task', {'scene_id': scene.id, 'stage': 'memory'}))
    broken = json.loads(json.dumps(MEMORY))
    del broken['core']['marta']['body']
    result = call(server, 'save_stage_result', {'scene_id': scene.id, 'stage': 'memory', 'task_fingerprint': task['task_fingerprint'],
                                                'result': json.dumps(broken, ensure_ascii=False)})
    assert result.is_error and '422' in text(result) and 'core.marta.body' in text(result)
    assert 'memory' not in repo.get_scene(scene.id).heads


@pytest.mark.req('MCP-BRIDGE')
def test_scene_context_carries_instructions(tmp_path):
    """MCP-BRIDGE-S46."""
    app, http, repo, story, scene = scene_with_prose(tmp_path)
    data = ok(call(build_server(http), 'get_scene_context', {'scene_id': scene.id}))
    assert data['instructions'] and data['instructions_error'] is None


@pytest.mark.req('MCP-BRIDGE')
def test_next_steps_suggests_memory_after_prose(tmp_path):
    app, http, repo, story, scene = scene_with_prose(tmp_path)
    writes = spy_writes(http)
    steps = text(call(build_server(http), 'next_steps', {'scene_id': scene.id}))
    assert "get_stage_task(stage='memory')" in steps
    assert writes == []
