import json
import threading

import httpx
import pytest

from storygen.providers.streaming import build_generation_gateway
from tests.providers.test_venice import context, model


def _stream_body():
    chunks = [
        {'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'qwen-test', 'choices': [{'index': 0, 'delta': {'content': 'Готово.'}, 'finish_reason': None}]},
        {'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'qwen-test', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
        {'id': 'r', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'qwen-test', 'choices': [], 'usage': {'prompt_tokens': 10, 'completion_tokens': 3, 'total_tokens': 13}},
    ]
    return ''.join('data: ' + json.dumps(c) + '\n\n' for c in chunks) + 'data: [DONE]\n\n'


def run(monkeypatch, accounted_call, catalog_row=None, catalog_status=200, grant=False):
    monkeypatch.setenv('VENICE_API_KEY', 'test')
    requests, reservations = [], []
    def handler(request):
        requests.append(request)
        if request.method == 'GET':
            if catalog_status != 200:
                return httpx.Response(catalog_status, json={'error': 'x'})
            return httpx.Response(200, json={'data': [catalog_row]})
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=_stream_body())
    ctx = context().model_copy(update={'policy_role': 'writer', 'policy_rating': (2, 0, 0)})
    accounting = accounted_call('venice', 'qwen-test')
    original = accounting.before
    def spy(*args, **kwargs):
        reservations.append(1)
        return original(*args, **kwargs)
    accounting.before = spy
    if grant:
        accounting.repo.model_policy('set_consent', role='writer', provider='venice', base_url=ctx.settings.provider.base_url, model='qwen-test')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events = list(build_generation_gateway(ctx.settings.provider, client, accounting).stream(ctx, threading.Event()))
    posts = [r for r in requests if r.method == 'POST']
    return events, posts, reservations


@pytest.mark.req('MODEL-003')
def test_gateway_blocks_venice_model_without_consent_before_sending(monkeypatch, accounted_call):  # MODEL-003-S02
    events, posts, reservations = run(monkeypatch, accounted_call, model(uncensored=False))
    assert events[-1].type == 'error' and events[-1].failure['category'] == 'model_policy'
    assert events[-1].message == events[-1].failure['message']
    assert posts == [] and reservations == []


@pytest.mark.req('MODEL-003')
def test_gateway_lets_uncensored_venice_model_through(monkeypatch, accounted_call):
    events, posts, reservations = run(monkeypatch, accounted_call, model(uncensored=True))
    assert events[-1].type == 'terminal' and len(posts) == 1 and reservations == [1]


@pytest.mark.req('MODEL-003')
def test_gateway_lets_consented_venice_model_through(monkeypatch, accounted_call):
    events, posts, reservations = run(monkeypatch, accounted_call, model(uncensored=False), grant=True)
    assert events[-1].type == 'terminal' and len(posts) == 1 and reservations == [1]


@pytest.mark.req('MODEL-003')
def test_gateway_catalog_failure_does_not_bypass_check(monkeypatch, accounted_call):
    events, posts, reservations = run(monkeypatch, accounted_call, catalog_status=500)
    assert events[-1].type == 'error' and events[-1].failure['category'] != 'model_policy'
    assert posts == [] and reservations == []
