"""SECURITY-002: every reader of a provider key goes through providers.secrets, so a key from the OS store works
everywhere a key from the environment does — including the redaction of provider error texts."""
import re
import threading
from pathlib import Path

import httpx
import pytest

from storygen.generation.context import ContextBundle
from storygen.providers.client import ProviderConfigurationError, build_openai_client
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import build_generation_gateway

STORED = 'stored-synthetic-key'


@pytest.fixture(autouse=True)
def no_keys_in_environment(monkeypatch):
    for name in ('OPENROUTER_API_KEY', 'VENICE_API_KEY'):
        monkeypatch.delenv(name, raising=False)


def test_client_takes_the_key_from_the_store(secret_store):
    secret_store.set('OPENROUTER_API_KEY', STORED)
    assert build_openai_client(ProviderSettings(provider='openrouter', model='m')).api_key == STORED


def test_client_without_any_key_keeps_the_configuration_error(secret_store):
    with pytest.raises(ProviderConfigurationError, match='Ключ провайдера відсутній'):
        build_openai_client(ProviderSettings(provider='venice', model='m'))


def test_environment_key_still_wins_for_the_client(secret_store, monkeypatch):
    secret_store.set('OPENROUTER_API_KEY', STORED)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'from-env')
    assert build_openai_client(ProviderSettings(provider='openrouter', model='m')).api_key == 'from-env'


def test_evaluator_gateway_takes_the_key_from_the_store(secret_store):
    from storygen.evaluation.gateway import OpenAICompatibleGateway
    from storygen.evaluation.models import EvaluatorConfig
    secret_store.set('VENICE_API_KEY', STORED)
    gateway = OpenAICompatibleGateway(EvaluatorConfig(provider='venice', model='m', max_input_chars=1000))
    assert gateway.client.api_key == STORED


def test_stored_key_is_redacted_from_provider_errors(secret_store):
    secret_store.set('SYNTHETIC_PROVIDER_KEY', STORED)
    settings = RoleSettings(provider=ProviderSettings(provider='local', model='test', key_env='SYNTHETIC_PROVIDER_KEY'),
                            max_output_tokens=1000, context_tokens=8192)
    ctx = ContextBundle(story_id='s', scene_id='c', stage='draft', scene_revision=0, story_revision=0, settings=settings,
                        system_text='system', user_text='user text', input_refs=[], fingerprint='f', estimated_tokens=10)
    reply = httpx.Response(400, json={'error': {'code': 'invalid_parameter', 'message': f'bad key {STORED}'}})
    with httpx.Client(transport=httpx.MockTransport(lambda _: reply)) as client:
        event = list(build_generation_gateway(ctx.settings.provider, client).stream(ctx, threading.Event()))[-1]
    assert event.type == 'error' and STORED not in event.message and STORED not in str(event.failure)
    # The assertions above must come from the redaction of this very HTTP 400, not from an unrelated failure.
    assert (event.failure['category'], event.failure['http_status'], event.failure['provider_code']) == ('provider_error', 400, 'invalid_parameter')
    assert event.failure['provider_message'] == 'bad key [ключ приховано]'


def test_key_replaced_during_a_request_is_still_redacted(secret_store, accounted_call):
    # The credential the request was sent with is the one to hide, even if the store changed before the error came back.
    secret_store.set('OPENROUTER_API_KEY', STORED)
    settings = RoleSettings(provider=ProviderSettings(provider='openrouter', model='test'), max_output_tokens=1000, context_tokens=8192)
    ctx = ContextBundle(story_id='s', scene_id='c', stage='draft', scene_revision=0, story_revision=0, settings=settings,
                        system_text='system', user_text='user text', input_refs=[], fingerprint='f', estimated_tokens=10)

    def handler(request):
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': 'test', 'object': 'model', 'context_length': 200000}]})
        secret_store.delete('OPENROUTER_API_KEY')
        return httpx.Response(400, json={'error': {'code': 'invalid_parameter', 'message': f'bad key {STORED}'}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        event = list(build_generation_gateway(ctx.settings.provider, client, accounted_call('openrouter', 'test')).stream(ctx, threading.Event()))[-1]
    assert event.type == 'error' and event.failure.get('http_status') == 400, event
    assert STORED not in event.message and STORED not in str(event.failure)
    assert event.failure['provider_message'] == 'bad key [ключ приховано]'


def test_no_direct_environment_reads_of_keys_remain():
    root = Path(__file__).resolve().parents[2] / 'src' / 'storygen'
    pattern = re.compile(r'os\.environ\.get\([^)]*key', re.IGNORECASE)
    offenders = [f'{path.relative_to(root)}:{number}' for path in root.rglob('*.py') if path.name != 'secrets.py'
                 for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1) if pattern.search(line)]
    assert offenders == []
