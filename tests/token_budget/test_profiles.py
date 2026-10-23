from datetime import datetime, timedelta, timezone
import pytest

from storygen.token_budget.core import measure, estimate, build_profile


def body(text):
    return {'model': 'model-a', 'messages': [{'role': 'user', 'content': text}], 'max_tokens': 50}


def observation(text, tokens=100):
    item = measure('venice', 'https://api.venice.ai/api/v1', body(text))
    return {**item, 'prompt_tokens': tokens, 'source_id': item['request_hash']}


def samples():
    return [observation(('Слово ' * (i * 20 + 1)) if i % 3 == 0 else
        ('english ' * (i * 20 + 1)) if i % 3 == 1 else
        '{"text":"' + ('value ' * (i * 20 + 1)) + '"}', 100 + i * 30) for i in range(90)]


def test_fallback_includes_entire_body_and_schema():
    first = measure('venice', 'https://api.venice.ai/api/v1', body('Привіт'))
    request = {**body('Привіт'), 'response_format': {'schema': {'description': 'x' * 900}}}
    second = measure('venice', 'https://api.venice.ai/api/v1', request)
    assert estimate(first)['input_tokens'] == first['body_bytes'] + 256
    assert estimate(second)['input_tokens'] > estimate(first)['input_tokens'] + 800
    assert first['identity'] != second['identity']


def test_profile_requires_distinct_samples_and_never_auto_activates():
    short = observation('hello')
    rejected = build_profile([short] * 48)
    assert not rejected['eligible'] and 'insufficient_samples' in rejected['reasons']
    profile = build_profile(samples())
    assert profile['eligible'], profile['reasons']
    assert not profile['active']
    assert profile['holdout_min_surplus_tokens'] >= 0
    assert profile['margin_multiplier'] == 1.20
    item = samples()[45]
    assert estimate(item, profile)['method'] == 'utf8_body_conservative'
    profile['active'] = True
    result = estimate(item, profile)
    assert result['method'] == 'verified_empirical_profile'
    assert result['input_tokens'] >= item['prompt_tokens']


def test_profile_has_expiry_identity_and_range_guards():
    rows = samples(); profile = build_profile(rows); profile['active'] = True
    changed = {**rows[45], 'identity': 'different-model'}
    assert estimate(changed, profile)['method'] == 'utf8_body_conservative'
    assert estimate({**rows[45], 'body_bytes': profile['max_bytes'] + 1}, profile)['method'] == 'utf8_body_conservative'
    future = datetime.now(timezone.utc) + timedelta(days=8)
    assert estimate(rows[45], profile, now=future)['method'] == 'utf8_body_conservative'


def test_inadequate_class_and_size_coverage_rejected():
    rows = [observation('english ' + str(i) + 'x' * 100, 100) for i in range(50)]
    profile = build_profile(rows)
    assert not profile['eligible']
    assert 'insufficient_size_range' in profile['reasons']
    assert 'insufficient_content_coverage' in profile['reasons']


def test_observation_identity_normalizes_loopback_and_separates_modes():
    first = measure('local', 'http://localhost:1235/v1/', body('a'))
    second = measure('local', 'http://127.0.0.1:1235/v1', body('b'))
    assert first['identity'] == second['identity']
    assert first['request_hash'] != second['request_hash']
    assert measure('local', 'http://localhost:1235/v1', {**body('a'), 'model': 'b'})['identity'] != first['identity']


def test_missing_or_invalid_usage_cannot_build_profile():
    for invalid in (None, 0, -1, True, 1.5):
        profile = build_profile([{**observation('hello'), 'prompt_tokens': invalid}])
        assert not profile['eligible']


def test_holdout_underestimate_rejects_profile():
    rows = samples()
    sorted_rows = sorted(rows, key=lambda r: r['request_hash'])
    sorted_rows[-1]['prompt_tokens'] = 10**8
    profile = build_profile(rows)
    assert not profile['eligible'] and 'holdout_underestimate' in profile['reasons']
