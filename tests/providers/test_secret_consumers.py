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


def test_no_direct_environment_reads_of_keys_remain():
    root = Path(__file__).resolve().parents[2] / 'src' / 'storygen'
    pattern = re.compile(r'os\.environ\.get\([^)]*key', re.IGNORECASE)
    offenders = [f'{path.relative_to(root)}:{number}' for path in root.rglob('*.py') if path.name != 'secrets.py'
                 for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1) if pattern.search(line)]
    assert offenders == []
