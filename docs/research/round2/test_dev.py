"""Dev never reads approved holdout and stops at qualification gates."""
import pytest


def test_dev_uses_eight_old_cases_only():
    from .dev import old_cases
    cases=old_cases()
    assert len(cases)==8 and len({c['id'] for c in cases})==8
    assert cases[0]['id']=='letter-clean' and cases[-1]['id']=='violence-issue'
    assert all(len(c['sources'])==1 for c in cases)


def test_dev_stops_on_reasoning_unknown_or_present():
    from .dev import qualification_error
    good=dict(status='valid',reasoning_tokens=0,reasoning_chars=0,seconds=2)
    assert qualification_error('L1',good) is None
    assert 'reasoning' in qualification_error('L1',dict(good,reasoning_tokens=None))
    assert 'reasoning' in qualification_error('L1',dict(good,reasoning_tokens=1))
    assert 'reasoning' in qualification_error('L1',dict(good,reasoning_chars=1))
    assert '60' in qualification_error('L3',dict(good,seconds=61))
    assert qualification_error('L1',dict(good,seconds=61)) is None
    assert 'invalid' in qualification_error('L4',dict(good,status='invalid'))


def test_cloud_usage_settlement_keeps_unknown_reasoning_reserve():
    from .cloud import usage_cost
    assert usage_cost('gemini-3.5-flash-lite',dict(promptTokenCount=100,candidatesTokenCount=10),day='2026-10-29') is None


def test_dev_cloud_reserve_is_limited_to_approved_small_requests():
    from .dev import cloud_dev_reserve
    from .test_round2 import prepared
    assert str(cloud_dev_reserve(prepared(),'google',dict(model='gemini-3.5-flash-lite')))=='0.05'
    req=prepared();req['body']['messages'][1]['content']='x'*20000
    with pytest.raises(ValueError,match='bound'):
        cloud_dev_reserve(req,'google',dict(model='gemini-3.5-flash-lite'))
    with pytest.raises(ValueError):cloud_dev_reserve(prepared(),'anthropic',dict(model='claude-opus-5-5'))


def test_owner_approved_dev_completion_preserves_invalid_but_not_resource_gates():
    from .dev import stop_after
    bad=dict(status='invalid',reasoning_tokens=0,reasoning_chars=0,seconds=10)
    assert stop_after('L1',bad,False)
    assert not stop_after('L1',bad,True)
    assert stop_after('L1',dict(bad,reasoning_tokens=None),True)
    assert stop_after('L3',dict(bad,seconds=61),True)
    assert stop_after('L1',dict(bad,status='refusal'),True)
