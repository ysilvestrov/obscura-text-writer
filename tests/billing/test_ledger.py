from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pytest
from storygen.storage.repository import Repository
from storygen.billing.models import Tariff, money, BudgetError
from storygen.billing.service import set_limit, summary, reserve, mark_sent, settle, save_tariff


def tariff():
    return Tariff(provider='venice', model='m', base_url='https://api.venice.ai/api/v1',
        input_per_million='1', output_per_million='2', source='https://example.org/verified', kind='manual',
        expires_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat())


def setup(repo, cap='0.01'):
    set_limit(repo, 'cli:test', cap, expected_revision=0)
    save_tariff(repo, tariff())


def call(repo, id='a', **kwargs):
    return reserve(repo, scope='cli:test', run_id='run', call_id=id, provider='venice', model='m',
        base_url='https://api.venice.ai/api/v1', request_hash=id, input_tokens=1000, output_tokens=1000, **kwargs)


def test_money_and_missing_budget_fail_closed(tmp_path):
    repo = Repository(tmp_path)
    for value in ('NaN', 'Infinity', '-1', True):
        with pytest.raises(ValueError): money(value)
    assert money('0.0000000001') == 1
    with pytest.raises(BudgetError): call(repo)


def test_summary_last_call_tracks_send_order_not_later_settlement(tmp_path):
    repo=Repository(tmp_path);setup(repo)
    assert summary(repo,'cli:test')['last_call'] is None
    call(repo,'a')
    assert summary(repo,'cli:test')['last_call'] is None
    mark_sent(repo,'a')
    pending=summary(repo,'cli:test')['last_call']
    assert pending['state']=='sent' and pending['cost_source'] is None
    call(repo,'b');mark_sent(repo,'b')
    settle(repo,'b',usage={'prompt_tokens':100,'completion_tokens':100},complete=True)
    settle(repo,'a',usage={},reported_usd='0.001',complete=True)
    call(repo,'c')  # A reservation is not a sent call.
    last=summary(repo,'cli:test')['last_call']
    assert last['call_id']=='b'
    assert last['cost_source']=='priced_usage_estimate'
    assert last['counted_nanos']==money('0.0003')
    assert last['provider']=='venice' and last['model']=='m'
    assert last['usage']=={'prompt_tokens':100,'completion_tokens':100}
    assert pending['usage'] is None
    assert 'tariff' not in last and 'request_hash' not in last
    repo.billing('unpriced',scope='cli:other',call_id='other',run_id='other',provider='local',model='other')
    mark_sent(repo,'other')
    assert summary(repo,'cli:test')['last_call']['call_id']=='b'
    assert summary(repo,'cli:other')['last_call']['cost_source']=='unpriced'


def test_reserve_settle_and_unknown_are_not_free(tmp_path):
    repo = Repository(tmp_path); setup(repo)
    item = call(repo)
    assert item['reserved_nanos'] == money('0.003')
    with pytest.raises(BudgetError): call(repo)
    mark_sent(repo, 'a')
    settle(repo, 'a', usage={'prompt_tokens': 100, 'completion_tokens': 100}, complete=True)
    result = summary(repo, 'cli:test')
    assert result['estimated_nanos'] == money('0.0003') and result['actual_nanos'] == 0
    call(repo, 'b'); mark_sent(repo, 'b'); settle(repo, 'b', usage={}, complete=False)
    assert summary(repo, 'cli:test')['unresolved_nanos'] == money('0.003')
    call(repo, 'c')
    assert summary(repo, 'cli:test')['exposure_nanos'] == money('0.0063')


def test_atomic_reservation_and_run_cap(tmp_path):
    repo = Repository(tmp_path); setup(repo, '0.004')
    def attempt(id):
        try: call(repo, id); return True
        except BudgetError: return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, ['a', 'b'])) == [False, True]
    assert summary(repo, 'cli:test')['exposure_nanos'] == money('0.003')


def test_full_cost_and_overrun_are_preserved(tmp_path):
    repo = Repository(tmp_path); setup(repo)
    call(repo); mark_sent(repo, 'a')
    settle(repo, 'a', usage={}, reported_usd='0.02', complete=True)
    assert summary(repo, 'cli:test')['actual_nanos'] == money('0.02')
    with pytest.raises(BudgetError): call(repo, 'b')
    settle(repo, 'a', usage={}, reported_usd='0.02', complete=True)
    assert summary(repo, 'cli:test')['actual_nanos'] == money('0.02')


def test_expired_tariff_and_manual_source_required(tmp_path):
    repo = Repository(tmp_path); setup(repo)
    expired = tariff().model_copy(update={'expires_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()})
    with pytest.raises(ValueError): save_tariff(repo, expired)
    with pytest.raises(ValueError): Tariff(**{**tariff().model_dump(), 'source': ''})


def test_run_limit_and_diem_equivalent(tmp_path):
    repo=Repository(tmp_path);setup(repo)
    with pytest.raises(BudgetError):call(repo,run_limit_nanos=money('0.001'))
    call(repo);mark_sent(repo,'a')
    settle(repo,'a',usage={'prompt_tokens':100,'completion_tokens':100},reported_usd='0',reported_diem='0.4',complete=True)
    result=summary(repo,'cli:test')
    assert result['actual_nanos']==0 and result['estimated_nanos']==money('0.0003')


def test_unknown_reserve_and_cost_snapshot_survive_backup(tmp_path):
    from storygen.storage.backup import create_backup,restore_backup
    from storygen.storage.integrity import check_integrity
    repo=Repository(tmp_path/'source');setup(repo)
    call(repo);mark_sent(repo,'a');settle(repo,'a',usage={},complete=False)
    assert check_integrity(repo.root).ok
    restored=Repository(restore_backup(create_backup(repo.root,tmp_path/'backup'),tmp_path/'restored'))
    assert summary(restored,'cli:test')==summary(repo,'cli:test')
    row=restored.billing('calls',scope='cli:test')[0]
    assert row['state']=='unresolved' and row['tariff']['input_per_million']=='1'
