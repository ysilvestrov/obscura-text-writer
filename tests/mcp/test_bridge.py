"""MCP-BRIDGE: the stdio client translates tool calls into HTTP requests to a running Obscura."""
import json

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
def test_tool_list_is_exactly_the_twenty_one_tools(tmp_path):
    app, http = obscura(tmp_path)

    async def run():
        async with Client(build_server(http)) as client:
            return [tool.name for tool in (await client.list_tools()).tools]
    names = anyio.run(run)
    assert sorted(names) == sorted(TOOLS) == sorted(['list_stories', 'get_story', 'get_scene_context', 'import_plan_and_characters', 'save_draft', 'next_steps', 'get_scene_text',
                                                    'create_story', 'get_templates', 'update_story', 'add_scene', 'update_scene', 'open_ghost_mode',
                                                    'get_publication', 'update_publication', 'add_signature', 'upload_cover', 'export_book',
                                                    'get_settings', 'update_settings', 'apply_role_preset'])
    assert not [name for name in names if any(word in name for word in ('delete', 'trash', 'order', 'move'))]


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
    form_story = app.state.repo.create_story(StoryCreate(title='Маяк, форма'))
    result = call(build_server(http), 'import_plan_and_characters', {'story_id': story.id, 'plan_markdown': PLAN, 'characters_markdown': CHARACTERS})
    assert not result.is_error, text(result)
    form = http.post(f'/api/stories/{form_story.id}/sources', files=[('plan', ('plan.md', PLAN.encode(), 'text/markdown')),
                                                                    ('characters', ('characters.md', CHARACTERS.encode(), 'text/markdown'))])
    assert form.status_code == 200, form.text

    def outcome(data):
        return [(f['name'], f['kind'], f['status'], f['created_character_cards'], len(f['created_scene_ids']), f['warnings']) for f in data['files']], data['partial']
    assert outcome(result.structured_content) == outcome(form.json())
    assert [row[:5] for row in outcome(form.json())[0]] == [('plan.md', 'source_plan', 'imported', 0, 1), ('characters.md', 'source_characters', 'imported', 1, 0)]
    scenes = app.state.repo.context_view(story.id).list_scenes(story.id)
    assert [s.title for s in scenes] == ['Лист']
    assert list(http.get(f'/api/stories/{story.id}').json()['character_names'].values()) == ['Анна']


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
    draft = json.loads(text(call(server, 'get_scene_text', {'scene_id': scene.id, 'material': 'draft'})))
    ok = call(server, 'save_draft', {'scene_id': scene.id, 'text': 'Анна відчинила скриньку.', 'expected_revision': context['revision'],
                                     'context_fingerprint': context['context_fingerprint'], 'draft_version_id': draft['version_id'], 'model': 'sonnet'})
    assert not ok.is_error, text(ok)
    head = repo.get_version(repo.get_scene(scene.id).heads['draft'])
    assert head.external_origin.client == 'Claude Code' and head.external_origin.model == 'sonnet'
    stale = call(server, 'save_draft', {'scene_id': scene.id, 'text': 'Інше.', 'expected_revision': context['revision'],
                                        'context_fingerprint': context['context_fingerprint'], 'draft_version_id': head.id})
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
                                                           'context_fingerprint': context['context_fingerprint'], 'draft_version_id': None})
            return schema, result
    schema, result = anyio.run(run)
    assert not result.is_error, text(result)
    assert 'ctx' not in schema['properties']
    head = repo.get_version(repo.get_scene(scene.id).heads['draft'])
    assert head.external_origin.client == 'Claude Desktop' and head.external_origin.model is None


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('tool,arguments', [
    ('save_draft', {'scene_id': '../runs/RID/cancel?', 'text': 'x', 'expected_revision': 1, 'context_fingerprint': '0' * 64, 'draft_version_id': None}),
    ('save_draft', {'scene_id': 'S1', 'text': 'x', 'expected_revision': 1, 'context_fingerprint': '0' * 64, 'draft_version_id': '../trash'}),
    ('get_scene_text', {'scene_id': '../versions/X', 'material': 'draft'}),
    ('import_plan_and_characters', {'story_id': 'ID/impact/preview?', 'plan_markdown': PLAN}),
    ('get_story', {'story_id': '..'}),
    ('get_scene_context', {'scene_id': 'a/b'}),
    ('next_steps', {'scene_id': 'a?b'}),
    ('update_story', {'story_id': '../trash', 'expected_revision': 1, 'title': 'x'}),
    ('add_scene', {'story_id': 'ID/scene-order', 'title': 'x'}),
    ('add_scene', {'story_id': 'S1', 'title': 'x', 'character_ids': ['../x']}),
    ('update_scene', {'story_id': 'S1', 'scene_id': '../trash', 'expected_revision': 1, 'title': 'x'}),
    ('update_scene', {'story_id': 'S1', 'scene_id': 'C1', 'expected_revision': 1, 'plan_markdown': 'x', 'plan_version_id': '../v'}),
])
def test_identifiers_cannot_reach_other_endpoints(tool, arguments):
    seen = []

    def record(request):
        seen.append(request.url.path)
        return httpx.Response(200, json={})
    result = call(build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(record))), tool, arguments)
    assert result.is_error and 'ідентифікатор' in text(result)
    assert seen == []


def read_text(server, scene_id, material='draft', **extra):
    result = call(server, 'get_scene_text', {'scene_id': scene_id, 'material': material, **extra})
    assert not result.is_error, text(result)
    return json.loads(text(result))


def fresh_save(server, http, scene_id, body, draft_version_id):
    context = http.get(f'/api/scenes/{scene_id}/writing-context').json()
    return call(server, 'save_draft', {'scene_id': scene_id, 'text': body, 'expected_revision': context['revision'],
                                       'context_fingerprint': context['context_fingerprint'], 'draft_version_id': draft_version_id})


@pytest.mark.req('MCP-BRIDGE')
def test_get_scene_text_reads_the_current_draft(tmp_path):
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист', beats='Анна знаходить лист.'))
    server = build_server(http, client_name='Codex')
    assert read_text(server, scene.id)['version_id'] is None
    assert not fresh_save(server, http, scene.id, 'Анна відчинила скриньку.', None).is_error
    data = read_text(server, scene.id)
    assert data['version_id'] == repo.get_scene(scene.id).heads['draft'] and data['text'] == 'Анна відчинила скриньку.'
    assert data['external_origin']['client'] == 'Codex'
    assert read_text(server, scene.id, 'plan')['text'] == 'Анна знаходить лист.'


@pytest.mark.req('MCP-BRIDGE')
def test_save_draft_over_stale_draft_reaches_the_chat_as_409(tmp_path):
    # #108: fresh revision and fingerprint, but the chat rewrites the draft it read before the author's edit.
    app, http = obscura(tmp_path)
    repo = app.state.repo
    story = repo.create_story(StoryCreate(title='Маяк'))
    scene = repo.create_scene(story.id, SceneCreate(title='Лист', beats='Анна знаходить лист.'))
    server = build_server(http, client_name='Claude Code')
    assert not fresh_save(server, http, scene.id, 'Перша чернетка.', None).is_error
    seen = read_text(server, scene.id)
    author = http.post(f'/api/scenes/{scene.id}/draft', json={'text': 'Правка автора.', 'expected_revision': repo.get_scene(scene.id).revision})
    assert author.status_code == 200
    stale = fresh_save(server, http, scene.id, 'Перша чернетка з доданою фразою.', seen['version_id'])
    assert stale.is_error and '409' in text(stale) and 'get_scene_text' in text(stale)
    assert repo.get_scene(scene.id).heads['draft'] == author.json()['version']['id']


def _recording_server(seen):
    def record(request):
        seen.append(request.url.path)
        return httpx.Response(200, json={})
    return build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(record)))


@pytest.mark.req('MCP-BRIDGE')
def test_save_draft_requires_draft_version_id():
    seen = []
    result = call(_recording_server(seen), 'save_draft', {'scene_id': 'S1', 'text': 'x', 'expected_revision': 1, 'context_fingerprint': '0' * 64})
    assert result.is_error and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_material_outside_the_list_is_refused_without_request():
    seen = []
    result = call(_recording_server(seen), 'get_scene_text', {'scene_id': 'S1', 'material': '../../trash'})
    assert result.is_error and seen == []
