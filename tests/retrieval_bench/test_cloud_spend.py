import json
import os

import pytest

from memory_bench.cloud_spend import BudgetExceeded, LedgerMissing, SpendLedger


def test_ledger_missing_and_corrupt(tmp_path):
    with pytest.raises(LedgerMissing):
        SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0})
    (tmp_path / 'spend.json').write_text('{bad', encoding='utf-8')
    with pytest.raises(LedgerMissing):
        SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0})
    (tmp_path / 'spend.json').write_text('[]', encoding='utf-8')
    with pytest.raises(LedgerMissing):
        SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)


def test_error_messages_carry_only_the_code(tmp_path):
    with pytest.raises(LedgerMissing) as missing:
        SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 1.0})
    assert str(missing.value) == 'spend_ledger_missing'
    ledger = SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 1.0}, create=True)
    with pytest.raises(BudgetExceeded) as exceeded:
        ledger.check('anthropic', 2.0)
    assert str(exceeded.value) == 'cloud_budget_exceeded'


def test_create_writes_shape_and_keeps_existing(tmp_path):
    p = tmp_path / 'spend.json'
    SpendLedger.open(p, {'anthropic': 5.0}, create=True)
    data = json.loads(p.read_text(encoding='utf-8'))
    assert data['providers'] == {} and isinstance(data['prices_date'], str)
    a = SpendLedger.open(p, {'anthropic': 5.0}, create=True)
    a.record('anthropic', 1.5, 100, 20)
    assert SpendLedger.open(p, {'anthropic': 5.0}, create=True).spent('anthropic') == 1.5


def test_ledger_is_cumulative_across_opens(tmp_path):
    p = tmp_path / 'spend.json'
    a = SpendLedger.open(p, {'anthropic': 5.0}, create=True)
    a.record('anthropic', 3.0, 10, 5)
    b = SpendLedger.open(p, {'anthropic': 5.0})
    with pytest.raises(BudgetExceeded):
        b.check('anthropic', 2.5)
    b.check('anthropic', 1.9)
    b.check('anthropic', 2.0)  # exactly the cap is allowed
    assert json.loads(p.read_text(encoding='utf-8'))['providers']['anthropic'] == {
        'usd': 3.0, 'input_tokens': 10, 'output_tokens': 5, 'calls': 1}


def test_record_accumulates_and_leaves_no_tmp(tmp_path):
    p = tmp_path / 'spend.json'
    ledger = SpendLedger.open(p, {'anthropic': 5.0}, create=True)
    ledger.record('anthropic', 0.25, 10, 5)
    ledger.record('anthropic', 0.5, 20, 7)
    assert ledger.usage('anthropic') == {'usd': 0.75, 'input_tokens': 30, 'output_tokens': 12, 'calls': 2}
    assert not list(tmp_path.glob('*.tmp'))
    assert SpendLedger.open(p, {'anthropic': 5.0}).usage('anthropic')['calls'] == 2


def test_record_sees_spend_of_another_opened_ledger(tmp_path):
    p = tmp_path / 'spend.json'
    a = SpendLedger.open(p, {'anthropic': 5.0}, create=True)
    b = SpendLedger.open(p, {'anthropic': 5.0})
    a.record('anthropic', 1.0, 1, 1)
    b.record('anthropic', 1.0, 1, 1)
    assert SpendLedger.open(p, {'anthropic': 5.0}).spent('anthropic') == 2.0


def test_unknown_provider_has_no_budget(tmp_path):
    ledger = SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)
    with pytest.raises(BudgetExceeded):
        ledger.check('other', 0.0001)
    assert ledger.spent('other') == 0.0


def test_tmp_name_uses_pid(tmp_path, monkeypatch):
    seen = []
    real = os.replace

    def spy(a, b):
        seen.append(str(a))
        real(a, b)
    monkeypatch.setattr(os, 'replace', spy)
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)
    assert seen and seen[0].endswith(f'.{os.getpid()}.tmp')
