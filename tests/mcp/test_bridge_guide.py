"""MCP-BRIDGE S53: get_guide serves the Obscura skills to MCP clients that do not have them."""
import json
from pathlib import Path

import anyio
import httpx
import pytest

pytest.importorskip('mcp')
from mcp import Client  # noqa: E402

from storygen.mcp.bridge import INSTRUCTIONS, build_server  # noqa: E402

PLUGIN = Path(__file__).resolve().parents[2]/'integrations/claude/obscura'
SKILLS = ('start-story', 'draft-scene', 'publish', 'revise', 'series-bible', 'setup-models')


def server(plugin=PLUGIN):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    return build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=transport), plugin=plugin)


def call(srv, arguments):
    async def run():
        async with Client(srv) as client:
            return await client.call_tool('get_guide', arguments)
    return anyio.run(run)


def payload(result):
    assert not result.is_error, result.content
    return result.structured_content or json.loads(result.content[0].text)


def error(result):
    assert result.is_error
    return ''.join(getattr(item, 'text', '') for item in result.content)


@pytest.mark.req('MCP-BRIDGE')
def test_get_guide_returns_skill_and_reference_names():
    data = payload(call(server(), {'task': 'start-story'}))
    assert data['text'].startswith('---\nname: start-story')
    assert {'rules', 'interview'} <= set(data['references'])


@pytest.mark.req('MCP-BRIDGE')
def test_get_guide_reference():
    data = payload(call(server(), {'task': 'draft-scene', 'reference': 'continuity'}))
    assert data['text'] == (PLUGIN/'skills/draft-scene/references/continuity.md').read_text(encoding='utf-8')


@pytest.mark.req('MCP-BRIDGE')
def test_get_guide_refuses_unknown():
    message = error(call(server(), {'task': '../shared'}))
    assert all(skill in message for skill in SKILLS)
    message = error(call(server(), {'task': 'publish', 'reference': '..\\rules'}))
    assert 'rules' in message and 'Допустимі' in message


@pytest.mark.req('MCP-BRIDGE')
def test_get_guide_without_plugin():
    assert 'Провідник недоступний у цій збірці' in error(call(server(plugin=None), {'task': 'start-story'}))


@pytest.mark.req('MCP-BRIDGE')
def test_instructions_name_get_guide():
    assert 'get_guide' in INSTRUCTIONS
    assert all(skill in INSTRUCTIONS for skill in SKILLS)


@pytest.mark.req('MCP-BRIDGE')
def test_get_guide_serves_revise_skill_and_references():
    data = payload(call(server(), {'task': 'revise'}))
    assert data['text'].startswith('---\nname: revise')
    assert data['references'] == ['fact-change', 'local-edit', 'rules']


@pytest.mark.req('MCP-BRIDGE')
def test_get_guide_revise_reference():
    data = payload(call(server(), {'task': 'revise', 'reference': 'fact-change'}))
    assert data['text'] == (PLUGIN/'skills/revise/references/fact-change.md').read_text(encoding='utf-8')


@pytest.mark.req('MCP-BRIDGE')
def test_get_guide_revise_local_edit_points_to_fact_change_through_guide():
    data = payload(call(server(), {'task': 'revise', 'reference': 'local-edit'}))
    assert 'get_guide(task="revise", reference="fact-change")' in data['text']
    assert '${CLAUDE_PLUGIN_ROOT}' not in data['text']
