import json
import threading

import httpx
import pytest

from storygen.generation.context import ContextBundle
from storygen.providers.client import build_openai_client
from storygen.providers.discovery import discover_models
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import build_generation_gateway


def model(id='qwen-test', uncensored=True, schema=True, offline=False):
    return {'id': id, 'object': 'model', 'owned_by': 'venice.ai', 'model_spec': {
        'uncensored': uncensored, 'offline': offline, 'availableContextTokens': 128000,
        'capabilities': {'supportsResponseSchema': schema},
    }}


def test_venice_uses_only_its_official_endpoint_and_environment_key(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY', 'private-venice-test-key')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'other-test-key')
    settings = ProviderSettings(provider='venice', model='qwen-test')
    assert settings.base_url == 'https://api.venice.ai/api/v1'
    assert settings.key_env == 'VENICE_API_KEY'
    assert 'private-venice-test-key' not in settings.model_dump_json()
    with build_openai_client(settings) as client:
        assert client.api_key == 'private-venice-test-key' and client.max_retries == 0
    with pytest.raises(ValueError):
        ProviderSettings(provider='venice', model='x', base_url='https://example.com/api/v1')


def test_venice_discovery_requires_true_boolean_not_name_or_description(monkeypatch):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    missing = model('uncensored-in-name'); del missing['model_spec']['uncensored']
    rows = [model(), model('censored', False), missing, model('string-true', 'true'), model('offline', True, offline=True)]
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'data': rows})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        found = discover_models(ProviderSettings(provider='venice', model='discovery'), client)
    assert [m.id for m in found] == ['qwen-test']
    assert found[0].context_tokens == 128000 and found[0].uncensored is True
    assert len(requests) == 1 and requests[0].method == 'GET'
    assert requests[0].url.params['type'] == 'text'


def test_cancel_during_venice_catalog_does_not_start_paid_generation(monkeypatch, accounted_call):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    cancel = threading.Event()
    requests = []
    def handler(request):
        requests.append(request)
        cancel.set()
        return httpx.Response(200, json={'data': [model()]})
    ctx = context()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events = list(build_generation_gateway(ctx.settings.provider, client, accounted_call('venice','qwen-test')).stream(ctx, cancel))
    assert [r.method for r in requests] == ['GET']
    assert events[-1].type == 'cancelled'


def context(schema=False):
    settings = RoleSettings(provider=ProviderSettings(provider='venice', model='qwen-test', include_usage=True, response_mode='json_schema' if schema else 'prompt_json', venice_disable_thinking=True), memory_mode='evidence_delta')
    return ContextBundle(story_id='s', scene_id='c', stage='memory' if schema else 'draft', scene_revision=0, story_revision=0, settings=settings, system_text='Наш промпт', user_text='Точний авторський текст.', input_refs=[], fingerprint='f', estimated_tokens=10)


@pytest.mark.parametrize('available,schema', [(model(uncensored=False), False), (model(schema=False), True)])
def test_venice_generation_cannot_bypass_catalog_filter_or_schema_support(monkeypatch, available, schema, accounted_call):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'data': [available]})
    ctx = context(schema)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events = list(build_generation_gateway(ctx.settings.provider, client, accounted_call('venice','qwen-test')).stream(ctx, threading.Event()))
    assert events[-1].type == 'error'
    assert all(r.method == 'GET' for r in requests) and len(requests) == 1


def test_venice_stream_preserves_cost_and_explicit_vendor_options(monkeypatch, accounted_call):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    requests = []
    def handler(request):
        requests.append(request)
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [model()]})
        chunks = [
            {'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'qwen-test', 'choices': [{'index': 0, 'delta': {'content': 'Готово.'}, 'finish_reason': None}]},
            {'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'qwen-test', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
            {'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'qwen-test', 'choices': [], 'cost': {'usd': .001, 'diem': 0}, 'usage': {'prompt_tokens': 10, 'completion_tokens': 3, 'total_tokens': 13}},
        ]
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=''.join('data: '+json.dumps(c)+'\n\n' for c in chunks)+'data: [DONE]\n\n')
    ctx = context()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events = list(build_generation_gateway(ctx.settings.provider, client, accounted_call('venice','qwen-test')).stream(ctx, threading.Event()))
    assert events[-1].type == 'terminal' and events[-1].usage['cost'] == {'usd': .001, 'diem': 0}
    actual = json.loads(requests[-1].content)
    assert actual['venice_parameters']['include_venice_system_prompt'] is False
    assert actual['venice_parameters']['disable_thinking'] is True
    assert actual['venice_parameters']['enable_web_search'] == 'off'
    assert actual['messages'][1]['content'] == 'Точний авторський текст.'
    assert len(requests) == 2
