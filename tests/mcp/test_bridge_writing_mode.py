"""WRITING-MODE through the MCP bridge: the header on every request, the mode in story tools, refusals (S03, MCP-BRIDGE)."""
import pytest

pytest.importorskip('mcp')

from storygen.mcp.bridge import BRIDGE_HEADERS, build_client, build_server  # noqa: E402
from storygen.web.bridge_marker import BRIDGE_HEADER, OBSCURA_WRITES  # noqa: E402

from tests.mcp.test_bridge import call, obscura, text  # noqa: E402
from tests.mcp.test_bridge_settings import ok  # noqa: E402


def bridge(tmp_path):
    app, http = obscura(tmp_path)
    http.headers.update(BRIDGE_HEADERS)
    return app, http, build_server(http)


@pytest.mark.req('WRITING-MODE')
def test_bridge_client_marks_every_request():
    assert BRIDGE_HEADERS == {BRIDGE_HEADER: 'mcp'}
    with build_client('http://127.0.0.1:8765') as http:
        assert http.headers[BRIDGE_HEADER] == 'mcp'


@pytest.mark.req('WRITING-MODE')
def test_create_story_defaults_to_chat_and_story_tools_show_mode(tmp_path):
    app, http, server = bridge(tmp_path)
    created = ok(call(server, 'create_story', {'title': 'Маяк'}))
    assert created['writing_mode'] == 'chat'
    other = ok(call(server, 'create_story', {'title': 'Сад', 'writing_mode': 'obscura'}))
    assert other['writing_mode'] == 'obscura'
    assert ok(call(server, 'get_story', {'story_id': other['id']}))['writing_mode'] == 'obscura'
    listed = {row['id']: row['writing_mode'] for row in ok(call(server, 'list_stories'))['result']}
    assert listed == {created['id']: 'chat', other['id']: 'obscura'}
    refused = call(server, 'create_story', {'title': 'Ліс', 'writing_mode': 'both'})
    assert refused.is_error


@pytest.mark.req('WRITING-MODE')
def test_save_draft_in_obscura_mode_is_refused(tmp_path):
    app, http, server = bridge(tmp_path)
    story = ok(call(server, 'create_story', {'title': 'Сад', 'writing_mode': 'obscura'}))
    from storygen.domain import SceneCreate
    scene = app.state.repo.create_scene(story['id'], SceneCreate(title='Ранок', beats='Анна відчиняє скриньку.'))
    context = ok(call(server, 'get_scene_context', {'scene_id': scene.id}))
    result = call(server, 'save_draft', {'scene_id': scene.id, 'text': 'Анна відчинила скриньку.', 'expected_revision': context['revision'],
                                         'context_fingerprint': context['context_fingerprint'], 'draft_version_id': None})
    assert result.is_error and OBSCURA_WRITES in text(result)
    assert app.state.repo.get_scene(scene.id).heads.get('draft') is None
