"""MCP-BRIDGE: the stdio client translates tool calls into HTTP requests to a running Obscura."""
import anyio
import httpx
import pytest
from fastapi.testclient import TestClient

pytest.importorskip('mcp')
from mcp import Client  # noqa: E402
from mcp.types import Implementation  # noqa: E402

from storygen.application.settings import AppSettings  # noqa: E402
from storygen.domain import SceneCreate, StoryCreate  # noqa: E402
from storygen.mcp.bridge import TOOLS, build_server, check_url  # noqa: E402
from storygen.web.app import create_app  # noqa: E402

PLAN = '# План\n\nСцена 1: Лист\nХто бере участь: Анна.\nАнна знаходить лист.\n'
CHARACTERS = '# Персонажі\n\n## Анна\nДоглядачка маяка.\n'


def obscura(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path / 'data'))
    return app, TestClient(app, base_url='http://127.0.0.1:8765')


def call(server, name, arguments=None):
    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, arguments or {})
    return anyio.run(run)


def text(result):
    return ''.join(getattr(item, 'text', '') for item in result.content)


@pytest.mark.req('MCP-BRIDGE')
def test_tool_list_is_exactly_the_six_tools(tmp_path):
    app, http = obscura(tmp_path)

    async def run():
        async with Client(build_server(http)) as client:
            return [tool.name for tool in (await client.list_tools()).tools]
    names = anyio.run(run)
    assert sorted(names) == sorted(TOOLS) == sorted(['list_stories', 'get_story', 'get_scene_context', 'import_plan_and_characters', 'save_draft', 'next_steps'])


@pytest.mark.req('MCP-BRIDGE')
def test_server_not_running_is_a_tool_error_with_the_address(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    url = 'http://127.0.0.1:8799'

    def refused(request):
        raise httpx.ConnectError('connection refused', request=request)
    result = call(build_server(httpx.Client(base_url=url, transport=httpx.MockTransport(refused))), 'list_stories')
    assert result.is_error
    assert 'Obscura не запущено' in text(result) and url in text(result)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.req('MCP-BRIDGE')
def test_import_through_mcp_matches_the_form(tmp_path):
    app, http = obscura(tmp_path)
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    result = call(build_server(http), 'import_plan_and_characters', {'story_id': story.id, 'plan_markdown': PLAN, 'characters_markdown': CHARACTERS})
    assert not result.is_error, text(result)
    scenes = app.state.repo.context_view(story.id).list_scenes(story.id)
    assert [s.title for s in scenes] == ['Лист']
    assert 'Анна' in text(result) or '"files"' in text(result)


@pytest.mark.req('MCP-BRIDGE')
def test_import_without_plan_or_characters_is_refused(tmp_path):
    app, http = obscura(tmp_path)
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    result = call(build_server(http), 'import_plan_and_characters', {'story_id': story.id, 'plan_markdown': '  '})
    assert result.is_error and 'план або персонажів' in text(result)
    assert app.state.repo.context_view(story.id).list_scenes(story.id) == []


@pytest.mark.req('MCP-BRIDGE')
def test_save_draft_marks_the_external_client_and_conflicts_reach_the_chat(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист', beats='Анна знаходить лист.'))
    server = build_server(http, client_name='Claude Code')
    context = http.get(f'/api/scenes/{scene.id}/writing-context').json()
    ok = call(server, 'save_draft', {'scene_id': scene.id, 'text': 'Анна відчинила скриньку.', 'expected_revision': context['revision'],
                                     'context_fingerprint': context['context_fingerprint'], 'model': 'sonnet'})
    assert not ok.is_error, text(ok)
    head = repo.get_version(repo.get_scene(scene.id).heads['draft'])
    assert head.external_origin.client == 'Claude Code' and head.external_origin.model == 'sonnet'
    stale = call(server, 'save_draft', {'scene_id': scene.id, 'text': 'Інше.', 'expected_revision': context['revision'],
                                        'context_fingerprint': context['context_fingerprint']})
    assert stale.is_error and '409' in text(stale)
    assert repo.get_scene(scene.id).heads['draft'] == head.id


@pytest.mark.req('MCP-BRIDGE')
def test_get_story_reports_scene_states_with_the_ui_vocabulary(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    plain = repo.create_scene(story.id, SceneCreate(title='Перша'))
    drafted = repo.create_scene(story.id, SceneCreate(title='Друга'))
    draft = repo.save_version(story.id, drafted.id, 'draft', 'Текст.', [])
    repo.set_head(drafted.id, 'draft', draft.id, drafted.revision)
    result = call(build_server(http), 'get_story', {'story_id': story.id})
    assert not result.is_error, text(result)
    data = result.structured_content
    states = {s['id']: s['state'] for s in data['scenes']}
    assert states == {plain.id: 'not_started', drafted.id: 'draft'}


@pytest.mark.req('MCP-BRIDGE')
def test_next_steps_points_to_the_scene_in_obscura(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист'))
    result = call(build_server(http), 'next_steps', {'scene_id': scene.id})
    assert not result.is_error
    assert f'/stories/{story.id}?scene={scene.id}' in text(result)


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('url', ['http://example.com:8765', 'http://192.168.1.5:8765', 'ftp://127.0.0.1:8765'])
def test_non_loopback_url_stops_the_client(url):
    with pytest.raises(SystemExit):
        check_url(url)


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('url', ['http://127.0.0.1:8765', 'http://localhost:8770', 'http://[::1]:8765'])
def test_loopback_url_is_accepted(url):
    assert check_url(url) == url


@pytest.mark.req('MCP-BRIDGE')
def test_save_draft_takes_the_client_name_from_client_info(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист'))
    context = http.get(f'/api/scenes/{scene.id}/writing-context').json()
    server = build_server(http)

    async def run():
        async with Client(server, client_info=Implementation(name='Claude <Desktop>', version='1')) as client:
            schema = next(t for t in (await client.list_tools()).tools if t.name == 'save_draft').input_schema
            result = await client.call_tool('save_draft', {'scene_id': scene.id, 'text': 'Текст.', 'expected_revision': context['revision'],
                                                           'context_fingerprint': context['context_fingerprint']})
            return schema, result
    schema, result = anyio.run(run)
    assert not result.is_error, text(result)
    assert 'ctx' not in schema['properties']
    head = repo.get_version(repo.get_scene(scene.id).heads['draft'])
    assert head.external_origin.client == 'Claude Desktop' and head.external_origin.model is None
