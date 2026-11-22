"""OPENROUTER-REASONING through the MCP bridge: the field in update_settings and the model's capability in get_settings."""
import pytest

pytest.importorskip('mcp')

from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.providers.models import ModelOption, ReasoningCapability  # noqa: E402

from tests.mcp.test_bridge import call, obscura  # noqa: E402
from tests.mcp.test_bridge_settings import ok, put_role, story  # noqa: E402


def editor_fingerprint(server, story_id):
    return ok(call(server, 'get_settings', {'story_id': story_id}))['roles']['editor']['fingerprint']


@pytest.mark.req('OPENROUTER-REASONING')
def test_update_settings_sets_and_provider_switch_clears_the_field(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-test-not-a-real-key')
    app, http = obscura(tmp_path)
    created = story(app)
    put_role(http, created.id, 'editor', provider='openrouter', model='qwen/qwen3.8-flash')
    server = build_server(http)
    ok(call(server, 'update_settings', {'story_id': created.id, 'section': 'editor', 'expected_fingerprint': editor_fingerprint(server, created.id),
                                        'fields': {'openrouter_reasoning_effort': 'none'}}))
    assert app.state.repo.read_role_settings(created.id)['editor']['provider']['openrouter_reasoning_effort'] == 'none'
    ok(call(server, 'update_settings', {'story_id': created.id, 'section': 'editor', 'expected_fingerprint': editor_fingerprint(server, created.id),
                                        'fields': {'provider': 'local', 'model': 'm1'}}))
    assert 'openrouter_reasoning_effort' not in app.state.repo.read_role_settings(created.id)['editor']['provider']


@pytest.mark.req('OPENROUTER-REASONING')
def test_model_list_carries_the_reasoning_capability(tmp_path, monkeypatch):
    app, http = obscura(tmp_path)
    created = story(app)
    put_role(http, created.id, 'editor')
    monkeypatch.setattr('storygen.web.routes_settings.discover_models', lambda settings, http_client=None, *, repo=None: [
        ModelOption(id='glm', reasoning=ReasoningCapability(mandatory=True, default_enabled=True, efforts=['max', 'high', 'low'], default_effort='max')),
        ModelOption(id='plain')])
    data = ok(call(build_server(http), 'get_settings', {'story_id': created.id, 'models_for_role': 'editor'}))
    assert {item['id']: item['reasoning'] for item in data['models']} == {
        'glm': {'mandatory': True, 'default_enabled': True, 'efforts': ['max', 'high', 'low'], 'default_effort': 'max'}, 'plain': None}
