"""MCP-BRIDGE package 5: writing and model settings from the chat through the real Obscura app (S33-S37, S39)."""
import httpx
import pytest

pytest.importorskip('mcp')

from storygen.domain import SceneCreate, StoryCreate  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.providers.models import ModelOption  # noqa: E402

from tests.mcp.test_bridge import call, obscura, text  # noqa: E402

ROLES = ('planner', 'writer', 'editor', 'memory')


def ok(result):
    assert not result.is_error, text(result)
    return result.structured_content


def put_role(http, story_id, role, **provider):
    revision = http.get(f'/api/stories/{story_id}/settings').json()['story']['revision']
    response = http.put(f'/api/stories/{story_id}/settings', json={'expected_revision': revision, 'role': role, 'settings': {'provider': {'provider': 'local', 'model': 'm1', **provider}}})
    assert response.status_code == 200, response.text


def story(app):
    return app.state.repo.create_story(StoryCreate(title='Маяк', language='en'))


def spy_writes(http):
    writes = []
    original = http.request

    def spy(method, url, **kwargs):
        if method != 'GET':
            writes.append((method, str(url)))
        return original(method, url, **kwargs)
    http.request = spy
    return writes


@pytest.mark.req('MCP-BRIDGE')
def test_get_settings_of_a_new_story(tmp_path):
    app, http = obscura(tmp_path)
    created = story(app)
    data = ok(call(build_server(http), 'get_settings', {'story_id': created.id}))
    assert data['writing']['target_words'] == 7000 and data['writing']['fingerprint']
    assert {role: data['roles'][role]['configured'] for role in ROLES} == dict.fromkeys(ROLES, False)
    assert data['presets'] == [] and data['preset_fingerprint'] and 'prompts' not in data and 'models' not in data


@pytest.mark.req('MCP-BRIDGE')
def test_get_settings_shows_key_state_but_never_a_value(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-test-not-a-real-key')
    app, http = obscura(tmp_path)
    created = story(app)
    put_role(http, created.id, 'writer', provider='openrouter', model='vendor/model')
    server = build_server(http)
    data = ok(call(server, 'get_settings', {'story_id': created.id, 'include_prompts': True}))
    writer = data['roles']['writer']
    assert writer['configured'] and writer['model'] == 'vendor/model' and 'key_env' not in writer
    assert writer['key'] == {'name': 'OPENROUTER_API_KEY', 'source': 'env'}
    assert data['prompts']['writer'] and writer['custom_prompt'] is False
    assert 'sk-test-not-a-real-key' not in text(call(server, 'get_settings', {'story_id': created.id, 'include_prompts': True}))


@pytest.mark.req('MCP-BRIDGE')
def test_update_creates_a_role_and_then_changes_only_named_fields(tmp_path):
    app, http = obscura(tmp_path)
    created = story(app)
    server = build_server(http)
    fingerprint = ok(call(server, 'get_settings', {'story_id': created.id}))['roles']['writer']['fingerprint']
    refused = call(server, 'update_settings', {'story_id': created.id, 'section': 'writer', 'expected_fingerprint': fingerprint, 'fields': {'temperature': 0.9}})
    assert refused.is_error and 'model' in text(refused)
    first = ok(call(server, 'update_settings', {'story_id': created.id, 'section': 'writer', 'expected_fingerprint': fingerprint, 'fields': {'provider': 'local', 'model': 'm1'}}))
    # A new scene between reading and writing changes the story revision but not this section.
    app.state.repo.create_scene(created.id, SceneCreate(title='Сцена', beats='План.'))
    second = ok(call(server, 'update_settings', {'story_id': created.id, 'section': 'writer', 'expected_fingerprint': first['fingerprint'], 'fields': {'temperature': 0.9}}))
    assert second['settings']['model'] == 'm1' and second['settings']['temperature'] == 0.9
    assert second['changed'] == {'temperature': [0.7, 0.9]}


@pytest.mark.req('MCP-BRIDGE')
def test_update_writing_profile_keeps_other_fields(tmp_path):
    app, http = obscura(tmp_path)
    created = story(app)
    server = build_server(http)
    fingerprint = ok(call(server, 'get_settings', {'story_id': created.id}))['writing']['fingerprint']
    first = ok(call(server, 'update_settings', {'story_id': created.id, 'section': 'writing', 'expected_fingerprint': fingerprint, 'fields': {'genre': 'mystery', 'target_words': 9000}}))
    second = ok(call(server, 'update_settings', {'story_id': created.id, 'section': 'writing', 'expected_fingerprint': first['fingerprint'], 'fields': {'tone': 'dry'}}))
    assert (second['settings']['genre'], second['settings']['tone'], second['settings']['target_words']) == ('mystery', 'dry', 9000)


@pytest.mark.req('MCP-BRIDGE')
def test_section_changed_after_reading_is_refused_without_put(tmp_path):
    app, http = obscura(tmp_path)
    created = story(app)
    put_role(http, created.id, 'writer')
    server = build_server(http)
    fingerprint = ok(call(server, 'get_settings', {'story_id': created.id}))['roles']['writer']['fingerprint']
    put_role(http, created.id, 'writer', model='author-choice')
    writes = spy_writes(http)
    result = call(server, 'update_settings', {'story_id': created.id, 'section': 'writer', 'expected_fingerprint': fingerprint, 'fields': {'model': 'chat-choice'}})
    assert result.is_error and '409' in text(result) and 'get_settings' in text(result)
    assert writes == [] and http.get(f'/api/stories/{created.id}/settings').json()['roles']['writer']['provider']['model'] == 'author-choice'


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('section,fields', [
    ('writer', {'key_env': 'HOME_SECRET_X'}), ('writer', {'prompt_version_id': 'x'}), ('writer', {'classification': None}),
    ('writer', {'colour': 'red'}), ('writer', {}), ('writing', {'temperature': 1}), ('planner', {'edit_mode': 'diff'}), ('budget', {'limit_usd': 1}),
])
def test_forbidden_or_unknown_fields_are_refused_without_request(section, fields):
    seen = []

    def record(request):
        seen.append(request.url.path)
        return httpx.Response(200, json={})
    server = build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(record)))
    result = call(server, 'update_settings', {'story_id': 'S1', 'section': section, 'expected_fingerprint': '0' * 64, 'fields': fields})
    assert result.is_error and seen == []


@pytest.mark.req('MCP-BRIDGE')
def test_switching_provider_takes_the_new_providers_key_and_address(tmp_path):
    app, http = obscura(tmp_path)
    created = story(app)
    put_role(http, created.id, 'writer', key_env='MY_OWN_KEY')
    server = build_server(http)
    fingerprint = ok(call(server, 'get_settings', {'story_id': created.id}))['roles']['writer']['fingerprint']
    cloud = ok(call(server, 'update_settings', {'story_id': created.id, 'section': 'writer', 'expected_fingerprint': fingerprint, 'fields': {'provider': 'openrouter', 'model': 'vendor/model'}}))
    stored = http.get(f'/api/stories/{created.id}/settings').json()['roles']['writer']['provider']
    assert (stored['key_env'], stored['base_url']) == ('OPENROUTER_API_KEY', 'https://openrouter.ai/api/v1')
    ok(call(server, 'update_settings', {'story_id': created.id, 'section': 'writer', 'expected_fingerprint': cloud['fingerprint'], 'fields': {'provider': 'local', 'model': 'm2'}}))
    assert http.get(f'/api/stories/{created.id}/settings').json()['roles']['writer']['provider']['base_url'] == 'http://localhost:1235/v1'


def four_roles_and_preset(http, story_id, writer_key=None):
    for role in ROLES:
        put_role(http, story_id, role, **({'key_env': writer_key} if role == 'writer' and writer_key else {}))
    revision = http.get(f'/api/stories/{story_id}/settings').json()['story']['revision']
    saved = http.post(f'/api/stories/{story_id}/role-profiles/capture', json={'name': 'Набір', 'expected_revision': revision})
    assert saved.status_code == 200, saved.text
    return saved.json()['id']


@pytest.mark.req('MCP-BRIDGE')
def test_preset_is_previewed_then_applied(tmp_path):
    app, http = obscura(tmp_path)
    created = story(app)
    preset = four_roles_and_preset(http, created.id)
    put_role(http, created.id, 'writer', model='m2')
    server = build_server(http)
    data = ok(call(server, 'get_settings', {'story_id': created.id}))
    assert [item['id'] for item in data['presets']] == [preset]
    arguments = {'story_id': created.id, 'profile_id': preset, 'version': 1, 'expected_fingerprint': data['preset_fingerprint']}
    preview = ok(call(server, 'apply_role_preset', arguments))
    assert preview['applied'] is False and preview['roles']['writer']['changed'] == {'model': ['m2', 'm1']}
    assert http.get(f'/api/stories/{created.id}/settings').json()['roles']['writer']['provider']['model'] == 'm2'
    applied = ok(call(server, 'apply_role_preset', {**arguments, 'confirm': True}))
    assert applied['applied'] is True and http.get(f'/api/stories/{created.id}/settings').json()['roles']['writer']['provider']['model'] == 'm1'


@pytest.mark.req('MCP-BRIDGE')
def test_preset_with_a_foreign_key_name_is_not_applied(tmp_path):
    app, http = obscura(tmp_path)
    created = story(app)
    preset = four_roles_and_preset(http, created.id, writer_key='HOME_SECRET_X')
    put_role(http, created.id, 'writer')
    server = build_server(http)
    fingerprint = ok(call(server, 'get_settings', {'story_id': created.id}))['preset_fingerprint']
    writes = spy_writes(http)
    result = call(server, 'apply_role_preset', {'story_id': created.id, 'profile_id': preset, 'version': 1, 'expected_fingerprint': fingerprint, 'confirm': True})
    assert result.is_error and 'HOME_SECRET_X' in text(result)
    assert not [url for _, url in writes if url.endswith('/apply')]
    assert http.get(f'/api/stories/{created.id}/settings').json()['roles']['writer']['provider']['key_env'] == 'OPENROUTER_API_KEY'


def settings_payload(model='m1'):
    role = {'provider': {'provider': 'local', 'model': model, 'key_env': 'OPENROUTER_API_KEY'}, 'temperature': 0.7}
    return {'story': {'revision': 3, 'target_words': 7000, 'language': 'en', 'content_rating': None}, 'roles': dict.fromkeys(ROLES, role),
            'profile': {}, 'prompts': dict.fromkeys(ROLES, 'p'), 'prepare_prompt': 'q', 'prompt_contracts': {}, 'prepare_prompt_contract': None}


@pytest.mark.req('MCP-BRIDGE')
def test_evaluator_changed_after_reading_blocks_the_preset():
    state = {'evaluator': {'config': {'model': 'e1'}, 'block': None}}
    seen = []

    def serve(request):
        seen.append((request.method, request.url.path))
        path = request.url.path
        if path.endswith('/settings'):
            return httpx.Response(200, json=settings_payload())
        if path.endswith('/evaluator'):
            return httpx.Response(200, json=state['evaluator'])
        if path == '/api/role-profiles':
            return httpx.Response(200, json={'profiles': []})
        if path.startswith('/api/provider-keys/'):
            return httpx.Response(200, json={'name': 'OPENROUTER_API_KEY', 'source': None, 'stored': False, 'store_available': True})
        return httpx.Response(200, json={})
    server = build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(serve)))
    fingerprint = ok(call(server, 'get_settings', {'story_id': 'S1'}))['preset_fingerprint']
    state['evaluator'] = {'config': {'model': 'e2'}, 'block': None}
    result = call(server, 'apply_role_preset', {'story_id': 'S1', 'profile_id': 'P1', 'version': 1, 'expected_fingerprint': fingerprint, 'confirm': True})
    assert result.is_error and '409' in text(result)
    assert not [path for method, path in seen if method == 'POST']


@pytest.mark.req('MCP-BRIDGE')
def test_model_list_is_filtered_and_capped(tmp_path, monkeypatch):
    app, http = obscura(tmp_path)
    created = story(app)
    put_role(http, created.id, 'writer')
    asked = []

    def discover(settings, http_client=None, *, repo=None):
        asked.append(settings.provider)
        return [ModelOption(id=f'vendor/model-{index:03d}', context_tokens=32768) for index in range(250)] + [ModelOption(id='Other/Special')]
    monkeypatch.setattr('storygen.web.routes_settings.discover_models', discover)
    server = build_server(http)
    data = ok(call(server, 'get_settings', {'story_id': created.id, 'models_for_role': 'writer'}))
    assert asked == ['local'] and len(data['models']) == 200 and data['models_total'] == 251
    assert data['models'] == sorted(data['models'], key=lambda item: item['id'])
    special = ok(call(server, 'get_settings', {'story_id': created.id, 'models_for_role': 'writer', 'models_query': 'special'}))
    assert [item['id'] for item in special['models']] == ['Other/Special'] and special['models_total'] == 1
    for role in ('editor', 'budget'):
        assert call(server, 'get_settings', {'story_id': created.id, 'models_for_role': role}).is_error


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('tool,arguments', [
    ('get_settings', {'story_id': '..'}),
    ('update_settings', {'story_id': 'a/b', 'section': 'writer', 'expected_fingerprint': '0' * 64, 'fields': {'model': 'x'}}),
    ('apply_role_preset', {'story_id': 'S1', 'profile_id': '../x', 'version': 1, 'expected_fingerprint': '0' * 64}),
])
def test_identifiers_are_checked_before_the_request(tool, arguments):
    seen = []

    def record(request):
        seen.append(request.url.path)
        return httpx.Response(200, json={})
    result = call(build_server(httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(record))), tool, arguments)
    assert result.is_error and seen == []
