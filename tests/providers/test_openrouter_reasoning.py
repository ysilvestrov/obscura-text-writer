"""OPENROUTER-REASONING: the role's reasoning control for the OpenRouter provider."""
import pytest

from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.requests import generation_request, sdk_arguments, openrouter_reasoning


def role(**provider):
    return RoleSettings(provider=ProviderSettings(provider='openrouter', model='qwen/qwen3.8-flash', **provider))


@pytest.mark.parametrize('effort', ['minimal', 'low', 'medium', 'high', 'xhigh', 'max'])
def test_effort_goes_into_request_and_sdk_extra_body(effort):
    body = generation_request('edit', role(openrouter_reasoning_effort=effort), 'Система', 'Текст', {})
    assert body['reasoning'] == {'effort': effort}
    args = sdk_arguments(body)
    assert args['extra_body']['reasoning'] == {'effort': effort}
    assert 'reasoning' not in args


def test_none_disables_reasoning_with_documented_effort():
    # Probe П5 (22.11.2026): effort "none" gave 0 reasoning tokens on both Qwen models.
    body = generation_request('draft', role(openrouter_reasoning_effort='none'), 'Система', 'Текст', {})
    assert body['reasoning'] == {'effort': 'none'}


def test_empty_field_leaves_request_and_dump_unchanged():
    settings = role()
    assert openrouter_reasoning(settings.provider) == {}
    body = generation_request('edit', settings, 'Система', 'Текст', {})
    assert 'reasoning' not in body and 'provider' not in body
    assert 'openrouter_reasoning_effort' not in settings.provider.model_dump()
    assert 'openrouter_reasoning_effort' not in settings.model_dump()['provider']


def test_set_field_is_in_dump_so_fingerprints_follow_it():
    dumped = role(openrouter_reasoning_effort='low').model_dump()
    assert dumped['provider']['openrouter_reasoning_effort'] == 'low'
    assert ProviderSettings.model_validate(dumped['provider']).openrouter_reasoning_effort == 'low'


def test_stored_role_without_field_reads_as_empty():
    stored = role().model_dump()
    assert RoleSettings.model_validate(stored).provider.openrouter_reasoning_effort is None


@pytest.mark.parametrize('provider', ['venice', 'local'])
def test_field_is_rejected_for_other_providers(provider):
    with pytest.raises(ValueError):
        ProviderSettings(provider=provider, model='m', openrouter_reasoning_effort='low')


def test_other_providers_never_get_openrouter_reasoning():
    venice = RoleSettings(provider=ProviderSettings(provider='venice', model='m'))
    assert 'reasoning' not in generation_request('edit', venice, 'Система', 'Текст', {})


def catalog_option(reasoning=..., provider='openrouter'):
    from storygen.providers.catalog import model_option
    row = {'id': 'vendor/model', 'context_length': 128000, 'top_provider': {'max_completion_tokens': 16000}}
    if reasoning is not ...:
        row['reasoning'] = reasoning
    return model_option(provider, row)


def test_catalog_reads_mandatory_reasoning_with_its_efforts():
    # The live catalog row of z-ai/glm-5.3-flash on 22.11.2026 (probe П3).
    option = catalog_option({'mandatory': True, 'default_enabled': True, 'supported_efforts': ['max', 'high', 'low'], 'default_effort': 'max'})
    assert option.reasoning.model_dump() == {'mandatory': True, 'default_enabled': True, 'efforts': ['max', 'high', 'low'], 'default_effort': 'max'}


def test_catalog_omitted_efforts_mean_no_level_choice_and_null_means_all():
    assert catalog_option({'mandatory': False, 'default_enabled': True}).reasoning.efforts == []
    assert catalog_option({'mandatory': False, 'supported_efforts': None}).reasoning.efforts is None


def test_catalog_drops_unknown_efforts_and_ignores_malformed_objects():
    assert catalog_option({'mandatory': False, 'supported_efforts': ['high', 'turbo', 7]}).reasoning.efforts == ['high']
    assert catalog_option({'mandatory': 'yes'}).reasoning.mandatory is False
    assert catalog_option('broken').reasoning is None
    assert catalog_option().reasoning is None


def test_catalog_reasoning_is_openrouter_only():
    assert catalog_option({'mandatory': True}, provider='local').reasoning is None
