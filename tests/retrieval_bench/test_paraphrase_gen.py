import hashlib
import json
import os
import socket
import subprocess
import sys

import pytest

import rag_paraphrases as cli
from memory_bench.cloud_spend import BudgetExceeded, SpendLedger
from memory_bench.paraphrase import LEVELS, ROOT, Query, check_owner_file, manifest, snapshot_hash
from memory_bench.paraphrase_gen import (HAIKU, PRICE_IN, PRICE_OUT, PROMPT, PROMPT_ID, RECORD_PREFIX, generate)
from tests.retrieval_bench.helpers import rec, rich_records, scene

RECORD = rec('r1', 'facts', 'Ключ від ліхтарної кімнати лежить у бляшанці')
OK_SAME = 'Знову ключ у бляшанці'
BAD_SYN = 'Знову ключі в бляшанках'
OK_SYN = 'Чим відмикають замок'
OK_DESC = 'Металева коробка'
BAD_DESC = 'Знову ключ і кімната'
ALL_OK = {'same': OK_SAME, 'syn': OK_SYN, 'desc': OK_DESC}


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        return (reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)), 1000, 100


def _ledger(tmp_path, cap=5.0):
    return SpendLedger.open(tmp_path / 'spend.json', {'anthropic': cap}, create=True)


def _by_level(queries):
    return {q.level: q for q in queries}


def test_constants():
    assert HAIKU == 'claude-haiku-5-5' and (PRICE_IN, PRICE_OUT) == (0.10, 0.50)
    assert PROMPT_ID == hashlib.sha256(PROMPT.encode('utf-8')).hexdigest()


def test_generate_retries_and_rejects(tmp_path):
    client = FakeClient([{'same': OK_SAME, 'syn': BAD_SYN, 'desc': BAD_DESC},
                         {'same': 'не береться, рівень вже є', 'syn': OK_SYN, 'desc': BAD_DESC},
                         {'same': 'x', 'syn': 'y', 'desc': BAD_DESC}])
    ledger = _ledger(tmp_path)
    out = _by_level(generate([RECORD], [], client, ledger))
    assert (out['same'].text, out['same'].status) == (OK_SAME, 'ok')
    assert (out['syn'].text, out['syn'].status) == (OK_SYN, 'ok')
    assert (out['desc'].text, out['desc'].status) == (BAD_DESC, 'rejected')
    sha = hashlib.sha256(RECORD.text.encode('utf-8')).hexdigest()
    assert all(q.claim_id == 'r1' and q.record_sha256 == sha for q in out.values())
    usage = ledger.usage('anthropic')
    assert len(client.prompts) == 3 and usage['calls'] == 3
    assert usage['input_tokens'] == 3000 and usage['output_tokens'] == 300
    assert usage['usd'] == pytest.approx(3 * (1000 * PRICE_IN + 100 * PRICE_OUT) / 1e6)


def test_generate_stops_when_all_levels_fixed(tmp_path):
    client = FakeClient([ALL_OK])
    out = generate([RECORD], [], client, _ledger(tmp_path))
    assert len(client.prompts) == 1 and all(q.status == 'ok' for q in out)


def test_generate_bad_json_counts_as_attempt(tmp_path):
    client = FakeClient(['це не json', '{"same": 1', ALL_OK])
    ledger = _ledger(tmp_path)
    out = generate([RECORD], [], client, ledger)
    assert all(q.status == 'ok' for q in out) and ledger.usage('anthropic')['calls'] == 3
    client = FakeClient(['погано', 'погано', 'погано', 'не має бути викликано'])
    out = generate([RECORD], [], client, ledger)
    assert len(client.prompts) == 3
    assert all((q.status, q.text) == ('rejected', '') for q in out)


def test_generate_missing_or_non_string_value_is_a_failed_attempt(tmp_path):
    client = FakeClient([{'same': OK_SAME, 'syn': 5, 'desc': None}, ALL_OK])
    out = _by_level(generate([RECORD], [], client, _ledger(tmp_path)))
    assert len(client.prompts) == 2 and all(q.status == 'ok' for q in out.values())


def test_generate_accepts_json_in_code_fence(tmp_path):
    fenced = '```json\n' + json.dumps(ALL_OK, ensure_ascii=False) + '\n```'
    out = generate([RECORD], [], FakeClient([fenced]), _ledger(tmp_path))
    assert all(q.status == 'ok' for q in out)


def test_generate_names_are_sent_and_not_counted(tmp_path):
    record = rec('r2', 'facts', 'Марія ховає ключ у бляшанці')
    client = FakeClient([{'same': 'Марія ключ', 'syn': 'x', 'desc': 'y'}] * 3)
    out = _by_level(generate([record], ['Марія'], client, _ledger(tmp_path)))
    assert out['same'].status == 'rejected'  # one content word is shared, the name does not count
    assert 'Марія' in client.prompts[0] and record.text in client.prompts[0]
    assert PROMPT in client.prompts[0] and 'facts' in client.prompts[0]


def test_generate_checks_budget_before_each_call(tmp_path):
    ledger = _ledger(tmp_path, cap=0.0)
    client = FakeClient([ALL_OK])
    with pytest.raises(BudgetExceeded):
        generate([RECORD], [], client, ledger)
    assert client.prompts == [] and ledger.usage('anthropic')['calls'] == 0


def test_generate_is_per_record_in_order(tmp_path):
    r2 = rec('r2', 'facts', 'Маяк стоїть на високій скелі')
    second = {'same': 'Маяк на високій скелі', 'syn': 'Чим відмикають замок', 'desc': OK_DESC}
    out = generate([RECORD, r2], [], FakeClient([ALL_OK, second]), _ledger(tmp_path))
    assert [(q.claim_id, q.level) for q in out] == [(c, lv) for c in ('r1', 'r2') for lv in LEVELS]
    assert all(q.status == 'ok' for q in out)


def test_anthropic_client_constructs_without_network(monkeypatch):
    pytest.importorskip('anthropic')
    from memory_bench.paraphrase_gen import AnthropicClient

    def refuse(*a, **k):
        raise AssertionError('network')
    monkeypatch.setattr(socket, 'create_connection', refuse)
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    assert AnthropicClient('test-key-not-real').model == HAIKU


def test_anthropic_client_call_shape(monkeypatch):
    pytest.importorskip('anthropic')
    from memory_bench.paraphrase_gen import AnthropicClient
    client = AnthropicClient('test-key-not-real')
    seen = {}

    class Block:
        type, text = 'text', '{"a": 1}'

    class Thinking:
        type = 'thinking'

    class Usage:
        input_tokens, output_tokens = 12, 7

    class Reply:
        content, usage = [Thinking(), Block()], Usage()

    class Messages:
        def create(self, **kw):
            seen.update(kw)
            return Reply()
    monkeypatch.setattr(client, '_client', type('C', (), {'messages': Messages()})())
    assert client.complete('привіт') == ('{"a": 1}', 12, 7)
    assert seen['model'] == HAIKU and seen['max_tokens'] == 1024
    assert seen['output_config'] == {'effort': 'low'} and 'stream' not in seen
    assert seen['messages'] == [{'role': 'user', 'content': 'привіт'}]


# ---- CLI ----------------------------------------------------------------------------------------------------------

def _args(tmp_path, **over):
    base = {'--data': str(tmp_path / 'data'), '--story': 'abc', '--out': str(tmp_path / 'out'),
            '--manifest': str(tmp_path / 'manifest.json'), '--cloud-stories': 'abc',
            '--spend-ledger': str(tmp_path / 'spend.json'), '--env-file': str(tmp_path / 'env')}
    base.update(over)
    return [x for kv in base.items() for x in kv]


@pytest.fixture
def forbid_client(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('client constructed')
    monkeypatch.setattr(cli, 'make_client', boom)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)


@pytest.fixture
def story(monkeypatch):
    sc = scene(rich_records())
    monkeypatch.setattr(cli, 'load_story', lambda args: ('abc-story-id', [sc]))
    return sc


def _run(capsys, argv):
    code = cli.main(argv)
    return code, json.loads(capsys.readouterr().out)


def _env(tmp_path, text='ANTHROPIC_API_KEY=k\n'):
    (tmp_path / 'env').write_text(text, encoding='utf-8')


def test_cli_inside_repo_first(tmp_path, capsys, forbid_client, monkeypatch):
    monkeypatch.setattr(cli, 'load_story', lambda args: pytest.fail('story loaded'))
    out = ROOT / 'tests' / 'retrieval_bench' / 'no_such_out'
    code, res = _run(capsys, _args(tmp_path, **{'--out': str(out)}))
    assert (code, res) == (2, {'error': 'inside_repo'}) and not out.exists()


def test_cli_story_errors_pass_through(tmp_path, capsys, forbid_client, monkeypatch):
    def fail(args):
        raise cli.BenchError('live_data')
    monkeypatch.setattr(cli, 'load_story', fail)
    assert _run(capsys, _args(tmp_path))[1] == {'error': 'live_data'}


def test_cli_cloud_not_allowed(tmp_path, capsys, forbid_client, story):
    _env(tmp_path)
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)
    code, res = _run(capsys, _args(tmp_path, **{'--cloud-stories': 'zzz,'}))
    assert (code, res) == (2, {'error': 'cloud_not_allowed'})
    assert _run(capsys, _args(tmp_path, **{'--cloud-stories': ''}))[1] == {'error': 'cloud_not_allowed'}


def test_cli_ledger_missing_and_key_missing(tmp_path, capsys, forbid_client, story):
    _env(tmp_path)
    assert _run(capsys, _args(tmp_path))[1] == {'error': 'spend_ledger_missing'}
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)
    _env(tmp_path, '# nothing\nANTHROPIC_API_KEY=\n')
    assert _run(capsys, _args(tmp_path))[1] == {'error': 'anthropic_key_missing'}
    (tmp_path / 'env').unlink()
    assert _run(capsys, _args(tmp_path))[1] == {'error': 'anthropic_key_missing'}


def test_cli_exhausted_ledger_refuses_before_client(tmp_path, capsys, forbid_client, story):
    _env(tmp_path)
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True).record('anthropic', 6.0, 1, 1)
    assert _run(capsys, _args(tmp_path))[1] == {'error': 'cloud_budget_exceeded'}


def test_cli_init_spend_ledger(tmp_path, capsys, forbid_client):
    p = tmp_path / 'sub' / 'spend.json'
    code, res = _run(capsys, ['--init-spend-ledger', '--spend-ledger', str(p)])
    assert code == 0 and res['usd_spent'] == 0 and p.is_file()
    SpendLedger.open(p, {'anthropic': 5.0}).record('anthropic', 1.0, 1, 1)
    assert _run(capsys, ['--init-spend-ledger', '--spend-ledger', str(p)])[1]['usd_spent'] == 1.0


class SmartClient:
    """Answers from the record line of the prompt; syn and desc share no word with any record."""

    def complete(self, prompt):
        line = next(x for x in prompt.splitlines() if x.startswith(RECORD_PREFIX))
        return json.dumps({'same': line[len(RECORD_PREFIX):], 'syn': 'Нічого спільного зовсім',
                           'desc': 'Інше речення без збігів'}, ensure_ascii=False), 800, 80


def test_cli_happy_path_writes_outputs(tmp_path, capsys, monkeypatch, story):
    _env(tmp_path, 'export ANTHROPIC_API_KEY="k-not-real"\n')
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)
    keys = []
    monkeypatch.setattr(cli, 'make_client', lambda key: keys.append(key) or SmartClient())
    code, res = _run(capsys, _args(tmp_path, **{'--n': '4', '--owner-k': '3'}))
    assert code == 0 and keys == ['k-not-real']
    assert res['targets'] == 4 and res['queries_ok']['syn'] == res['queries_ok']['desc'] == 4
    # a record with a single content word can never give two shared words: its "same" is rejected after 3 attempts
    assert all(res['queries_ok'][lv] + res['rejected'][lv] == 4 for lv in LEVELS)
    assert res['queries_ok']['same'] >= 3 and res['rejected']['syn'] == res['rejected']['desc'] == 0
    rejected_same = res['rejected']['same']
    assert res['usd_spent'] == pytest.approx((4 + 2 * rejected_same) * (800 * PRICE_IN + 80 * PRICE_OUT) / 1e6, abs=1e-6)
    assert 'k-not-real' not in json.dumps(res)
    data = json.loads((tmp_path / 'out' / 'set.json').read_text(encoding='utf-8'))
    meta = data['meta']
    assert meta['story'] == 'abc-story-id' and meta['model'] == HAIKU and meta['prompt_id'] == PROMPT_ID
    assert {'seed', 'n', 'levels'} <= set(meta) and meta['levels'] == list(LEVELS)
    queries = [Query(**q) for q in data['queries']]
    assert len(queries) == 12 and all(q.text and q.record_sha256 for q in queries)
    snapshot = snapshot_hash(manifest(queries, meta))
    assert res['snapshot'] == snapshot
    mani = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    assert mani == {**manifest(queries, meta), 'snapshot': snapshot}
    assert not any(q.text in json.dumps(mani, ensure_ascii=False) for q in queries)
    owner_path = tmp_path / 'out' / 'owner-check.json'
    owner = json.loads(owner_path.read_text(encoding='utf-8'))
    assert owner['snapshot'] == snapshot and len(owner['items']) == 3
    assert check_owner_file(owner_path, queries, snapshot, expected=3)[0] == 'owner_check_missing'  # verdicts pending
    assert SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}).usage('anthropic')['calls'] == 4 + 2 * rejected_same


def test_cli_exceptions_hide_texts(tmp_path, capsys, monkeypatch, story):
    _env(tmp_path, 'ANTHROPIC_API_KEY=secret-key\n')
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)

    class Broken:
        def complete(self, prompt):
            raise RuntimeError('secret-key ' + prompt)
    monkeypatch.setattr(cli, 'make_client', lambda key: Broken())
    code, res = _run(capsys, _args(tmp_path, **{'--n': '2'}))
    assert (code, res) == (2, {'error': 'anthropic_call_failed', 'usd_spent': 0, 'records_done': 0})
    assert not (tmp_path / 'out' / 'set.json').exists()


def test_modules_import_without_numpy_and_anthropic():
    code = ("import sys; sys.modules['numpy']=None; sys.modules['anthropic']=None; "
            "import rag_paraphrases, memory_bench.paraphrase_gen, memory_bench.cloud_spend")
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT / 'scripts'), str(ROOT / 'src')])}
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 0, r.stderr


class CountingClient(SmartClient):
    """SmartClient that remembers which record lines it was asked about and can fail on the k-th distinct record."""

    def __init__(self, fail_on=None):
        self.records, self.fail_on = [], fail_on

    def complete(self, prompt):
        line = next(x for x in prompt.splitlines() if x.startswith(RECORD_PREFIX))
        if line not in self.records:
            self.records.append(line)
        if self.fail_on and len(self.records) == self.fail_on:
            raise RuntimeError('network ' + line)
        return super().complete(prompt)


def test_cli_rerun_after_failure_pays_only_for_unfinished_records(tmp_path, capsys, monkeypatch, story):
    _env(tmp_path)
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)
    failing = CountingClient(fail_on=3)
    monkeypatch.setattr(cli, 'make_client', lambda key: failing)
    code, res = _run(capsys, _args(tmp_path, **{'--n': '5'}))
    assert code == 2 and res['error'] == 'anthropic_call_failed' and res['records_done'] == 2
    assert res['usd_spent'] > 0 and set(res) == {'error', 'usd_spent', 'records_done'}
    assert not (tmp_path / 'out' / 'set.json').exists() and (tmp_path / 'out' / 'gen-cache.json').is_file()
    spent_first = SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}).spent('anthropic')
    assert res['usd_spent'] == pytest.approx(spent_first)
    working = CountingClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: working)
    code, res = _run(capsys, _args(tmp_path, **{'--n': '5'}))
    assert code == 0 and res['targets'] == 5
    assert working.records == failing.records[2:] + [r for r in working.records if r not in failing.records]
    assert len(working.records) == 3 and not set(working.records[:1]) & set(failing.records[:2])
    data = json.loads((tmp_path / 'out' / 'set.json').read_text(encoding='utf-8'))
    assert len(data['queries']) == 15 and all(q['text'] for q in data['queries'])
    assert res['usd_spent'] == pytest.approx(
        SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}).spent('anthropic') - spent_first, abs=1e-6)
    third = CountingClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: third)
    code, res = _run(capsys, _args(tmp_path, **{'--n': '5'}))
    assert code == 0 and third.records == [] and res['usd_spent'] == 0


def test_cli_cache_is_keyed_by_record_prompt_and_model(tmp_path, capsys, monkeypatch, story):
    _env(tmp_path)
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)
    monkeypatch.setattr(cli, 'make_client', lambda key: SmartClient())
    _run(capsys, _args(tmp_path, **{'--n': '2'}))
    entries = json.loads((tmp_path / 'out' / 'gen-cache.json').read_text(encoding='utf-8'))['entries']
    assert len(entries) == 2 and all(k.endswith(f'|{PROMPT_ID}|{HAIKU}') for k in entries)
    assert all(v['attempts'] >= 1 and len(v['queries']) == 3 for v in entries.values())
    monkeypatch.setattr(cli, 'PROMPT_ID', 'other-prompt')
    again = CountingClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: again)
    _run(capsys, _args(tmp_path, **{'--n': '2'}))
    assert len(again.records) == 2


def test_cli_budget_stop_reports_progress(tmp_path, capsys, monkeypatch, story):
    _env(tmp_path)
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)
    monkeypatch.setattr(cli, 'make_client', lambda key: SmartClient())
    code, res = _run(capsys, _args(tmp_path, **{'--n': '3', '--anthropic-max-usd': '0.0004'}))
    assert code == 2 and res['error'] == 'cloud_budget_exceeded' and res['records_done'] < 3 and 'usd_spent' in res


def test_cli_ledger_corrupted_mid_run_is_spend_ledger_missing(tmp_path, capsys, monkeypatch, story):
    _env(tmp_path)
    SpendLedger.open(tmp_path / 'spend.json', {'anthropic': 5.0}, create=True)

    class Corrupting(SmartClient):
        def complete(self, prompt):
            reply = super().complete(prompt)
            (tmp_path / 'spend.json').write_text('{bad', encoding='utf-8')
            return reply
    monkeypatch.setattr(cli, 'make_client', lambda key: Corrupting())
    code, res = _run(capsys, _args(tmp_path, **{'--n': '2'}))
    assert code == 2 and res['error'] == 'spend_ledger_missing' and res['records_done'] == 0


@pytest.mark.parametrize('message,code', [('live_data: refusing', 'live_data'), ('not_a_data_copy: x', 'not_a_data_copy'),
                                          ('C:/Users/someone/data does not exist', 'data_invalid'), ('', 'data_invalid')])
def test_data_error_codes_are_allowlisted(tmp_path, monkeypatch, message, code):
    import storygen.application.workspace_bench as wb

    def refuse(path, require):
        raise ValueError(message)
    monkeypatch.setattr(wb, '_check_data_dir', refuse)
    with pytest.raises(cli.BenchError) as error:
        cli.load_story(type('A', (), {'data': str(tmp_path), 'story': 'x'})())
    assert str(error.value) == code
