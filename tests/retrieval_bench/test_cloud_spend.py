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


# ---- Task 1 of the harness plan: caps in the ledger, shared key reading ------------------------------------------------

def test_ledger_persists_caps_once_and_takes_the_lower(outside_dir):
    path = outside_dir / 'spend.json'
    SpendLedger.open(path, {'anthropic': 5.0}, create=True)
    assert json.loads(path.read_text())['caps'] == {'anthropic': 5.0}
    raised = SpendLedger.open(path, {'anthropic': 50.0})
    assert raised.caps['anthropic'] == 5.0
    lowered = SpendLedger.open(path, {'anthropic': 1.0})
    assert lowered.caps['anthropic'] == 1.0
    assert json.loads(path.read_text())['caps'] == {'anthropic': 5.0}
    with pytest.raises(BudgetExceeded):
        raised.check('anthropic', 5.5)  # the argument's 50 does not lift the file's 5


def test_ledger_without_caps_field_gets_it_on_first_open(outside_dir):
    path = outside_dir / 'spend.json'
    old = {'providers': {'anthropic': {'usd': 0.073, 'input_tokens': 1, 'output_tokens': 2, 'calls': 3}},
           'prices_date': '2026-11-27'}
    path.write_text(json.dumps(old), encoding='utf-8')
    ledger = SpendLedger.open(path, {'anthropic': 5.0})
    after = json.loads(path.read_text())
    assert after['caps'] == {'anthropic': 5.0} and after['providers'] == old['providers']
    assert after['prices_date'] == '2026-11-27' and ledger.caps['anthropic'] == 5.0


def test_new_provider_cap_is_added_to_existing_caps(outside_dir):
    path = outside_dir / 'spend.json'
    SpendLedger.open(path, {'anthropic': 5.0}, create=True)
    ledger = SpendLedger.open(path, {'voyage': 1.0})
    assert json.loads(path.read_text())['caps'] == {'anthropic': 5.0, 'voyage': 1.0}
    assert ledger.caps == {'voyage': 1.0}
    again = SpendLedger.open(path, {'voyage': 9.0})
    assert again.caps['voyage'] == 1.0


def test_record_keeps_caps_in_the_file(outside_dir):
    path = outside_dir / 'spend.json'
    SpendLedger.open(path, {'anthropic': 5.0}, create=True).record('anthropic', 1.0, 1, 1)
    assert json.loads(path.read_text())['caps'] == {'anthropic': 5.0}


def test_malformed_caps_field_is_a_missing_ledger(outside_dir):
    path = outside_dir / 'spend.json'
    path.write_text(json.dumps({'providers': {}, 'caps': {'anthropic': 'five'}}), encoding='utf-8')
    with pytest.raises(LedgerMissing):
        SpendLedger.open(path, {'anthropic': 5.0})


def test_read_env_key_env_first_then_file_and_never_prints(monkeypatch, outside_dir, capsys):
    from memory_bench.cloud_spend import read_env_key
    env_file = outside_dir / 'env'
    env_file.write_text('# c\nOTHER=x\nexport MY_KEY = "from-file"\n', encoding='utf-8')
    monkeypatch.delenv('MY_KEY', raising=False)
    assert read_env_key('MY_KEY', env_file) == 'from-file'
    monkeypatch.setenv('MY_KEY', ' from-env ')
    assert read_env_key('MY_KEY', env_file) == 'from-env'
    monkeypatch.delenv('MY_KEY')
    env_file.write_text('#MY_KEY=commented\nMY_KEY=\n', encoding='utf-8')
    assert read_env_key('MY_KEY', env_file) == ''
    assert read_env_key('MY_KEY', outside_dir / 'absent') == ''
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
