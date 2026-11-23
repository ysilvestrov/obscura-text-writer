"""R-44 PR 4: the upper bound on the cost of an audit run, priced from the stored tariff only."""
from datetime import timedelta
from decimal import Decimal

from storygen.billing.models import Tariff, utcnow
from storygen.billing.service import save_tariff, set_limit
from storygen.generation.audit_cost import NO_PRICE, STALE_PRICE, upper_bound
from storygen.generation.readiness import preview
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.run_models import RunRequest
from storygen.storage.repository import Repository
from tests.generation.test_audit_context import auditor
from tests.generation.test_audit_verdict import unchecked_scene

ENDPOINTS = {'venice': 'https://api.venice.ai/api/v1', 'openrouter': 'https://openrouter.ai/api/v1'}


def cloud(provider='openrouter', model='cloud-model', max_input_chars=1000, max_output_tokens=1000):
    return RoleSettings(provider=ProviderSettings(provider=provider, model=model), max_input_chars=max_input_chars,
                        max_output_tokens=max_output_tokens)


def tariff(repo, provider='openrouter', model='cloud-model', days=1):
    return save_tariff(repo, Tariff(provider=provider, model=model, base_url=ENDPOINTS[provider], input_per_million='1',
                                    output_per_million='2', source='test tariff', kind='manual',
                                    expires_at=(utcnow() + timedelta(days=days)).isoformat()))


def test_cloud_with_a_current_tariff_prices_each_call_at_its_limits(tmp_path):
    repo = Repository(tmp_path)
    tariff(repo)
    # (1000*4+256) input tokens at $1/M + 1000 output tokens at $2/M = $0.006256 per call; three calls $0.018768.
    assert upper_bound(repo, cloud(), 3) == {'per_call_usd': '0.0063', 'total_usd': '0.0188', 'reason': None}
    stored = Tariff.model_validate(repo.billing('tariff_get', provider='openrouter', model='cloud-model',
                                                base_url=ENDPOINTS['openrouter']))
    per_call = stored.price(1000 * 4 + 256, 1000)
    assert Decimal(upper_bound(repo, cloud(), 3)['total_usd']) >= Decimal(per_call * 3) / 10**9


def test_venice_tariff_is_looked_up_by_the_settings_endpoint(tmp_path):
    repo = Repository(tmp_path)
    tariff(repo, provider='venice', model='venice-model')
    result = upper_bound(repo, cloud(provider='venice', model='venice-model'), 1)
    assert result == {'per_call_usd': '0.0063', 'total_usd': '0.0063', 'reason': None}


def test_stale_tariff_gives_no_usd_and_asks_to_refresh_prices(tmp_path, monkeypatch):
    repo = Repository(tmp_path)
    tariff(repo)
    later = utcnow() + timedelta(days=2)
    monkeypatch.setattr('storygen.billing.models.utcnow', lambda: later)
    assert STALE_PRICE == 'Ціна моделі застаріла; оновіть ціни в налаштуваннях'
    assert upper_bound(repo, cloud(), 2) == {'per_call_usd': None, 'total_usd': None, 'reason': STALE_PRICE}


def test_missing_tariff_gives_no_usd_and_says_so(tmp_path):
    repo = Repository(tmp_path)
    assert upper_bound(repo, cloud(), 2) == {'per_call_usd': None, 'total_usd': None, 'reason': NO_PRICE}


def test_broken_stored_tariff_never_raises(tmp_path, monkeypatch):
    repo = Repository(tmp_path)
    monkeypatch.setattr(repo, 'billing', lambda *_a, **_k: {'provider': 'openrouter'})
    assert upper_bound(repo, cloud(), 2) == {'per_call_usd': None, 'total_usd': None, 'reason': NO_PRICE}


def test_local_provider_has_no_usd_and_no_price_warning(tmp_path):
    repo = Repository(tmp_path)
    local = RoleSettings(provider=ProviderSettings(model='local-model'))
    assert upper_bound(repo, local, 2) == {'per_call_usd': None, 'total_usd': None, 'reason': None}
    assert upper_bound(repo, local, 0) == {'per_call_usd': None, 'total_usd': None, 'reason': None}


def test_no_calls_cost_nothing_even_without_a_tariff(tmp_path):
    repo = Repository(tmp_path)
    assert upper_bound(repo, cloud(), 0) == {'per_call_usd': None, 'total_usd': '0.0000', 'reason': None}
    tariff(repo)
    assert upper_bound(repo, cloud(), 0) == {'per_call_usd': '0.0063', 'total_usd': '0.0000', 'reason': None}


def scene_request(story, scene):
    return RunRequest(story_id=story.id, scene_id=scene.id, mode='audit', audit_scope='scene')


def test_readiness_carries_the_cost_of_a_cloud_auditor(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    auditor(repo, story, provider=ProviderSettings(provider='openrouter', model='cloud-model'), max_input_chars=1000,
            max_output_tokens=1000)
    tariff(repo)
    refused = preview(repo, scene_request(story, scene))
    # The missing story limit refuses the run, yet the preview still shows the price.
    assert refused['ready'] is False and refused['calls'] == 2
    assert refused['cost'] == {'per_call_usd': '0.0063', 'total_usd': '0.0126', 'reason': None}
    set_limit(repo, 'story:' + story.id, '10', 0)
    result = preview(repo, scene_request(story, scene))
    assert result['ready'] is True, result['reason']
    assert result['cost'] == {'per_call_usd': '0.0063', 'total_usd': '0.0126', 'reason': None}


def test_stale_tariff_does_not_make_the_preview_unready(tmp_path, monkeypatch):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    auditor(repo, story, provider=ProviderSettings(provider='openrouter', model='cloud-model'))
    tariff(repo)
    set_limit(repo, 'story:' + story.id, '10', 0)
    later = utcnow() + timedelta(days=2)
    monkeypatch.setattr('storygen.billing.models.utcnow', lambda: later)
    result = preview(repo, scene_request(story, scene))
    assert result['ready'] is True, result['reason']
    assert result['calls'] == 2 and result['cost'] == {'per_call_usd': None, 'total_usd': None, 'reason': STALE_PRICE}


def test_readiness_of_a_local_auditor_has_no_usd(tmp_path):
    repo, story, (scene,) = unchecked_scene(tmp_path)
    result = preview(repo, scene_request(story, scene))
    assert result['ready'] is True and result['cost'] == {'per_call_usd': None, 'total_usd': None, 'reason': None}


def test_readiness_without_a_configured_auditor_has_an_empty_cost(tmp_path):
    from storygen.generation.audit_run import readiness
    result = readiness(Repository(tmp_path), RunRequest.model_construct(story_id='missing', scene_id='x', mode='audit',
                                                                        audit_scope='scene'))
    assert result['ready'] is False and result['cost'] == {'per_call_usd': None, 'total_usd': None, 'reason': None}
