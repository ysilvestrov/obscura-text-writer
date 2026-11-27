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


def _ledger(outside_dir, cap=5.0):
    return SpendLedger.open(outside_dir / 'spend.json', {'anthropic': cap}, create=True)


def _by_level(queries):
    return {q.level: q for q in queries}


def test_constants():
    assert HAIKU == 'claude-haiku-5-5' and (PRICE_IN, PRICE_OUT) == (0.10, 0.50)
    assert PROMPT_ID == hashlib.sha256(PROMPT.encode('utf-8')).hexdigest()


def test_generate_retries_and_rejects(outside_dir):
    client = FakeClient([{'same': OK_SAME, 'syn': BAD_SYN, 'desc': BAD_DESC},
                         {'same': 'не береться, рівень вже є', 'syn': OK_SYN, 'desc': BAD_DESC},
                         {'same': 'x', 'syn': 'y', 'desc': BAD_DESC}])
    ledger = _ledger(outside_dir)
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


def test_generate_stops_when_all_levels_fixed(outside_dir):
    client = FakeClient([ALL_OK])
    out = generate([RECORD], [], client, _ledger(outside_dir))
    assert len(client.prompts) == 1 and all(q.status == 'ok' for q in out)


def test_generate_bad_json_counts_as_attempt(outside_dir):
    client = FakeClient(['це не json', '{"same": 1', ALL_OK])
    ledger = _ledger(outside_dir)
    out = generate([RECORD], [], client, ledger)
    assert all(q.status == 'ok' for q in out) and ledger.usage('anthropic')['calls'] == 3
    client = FakeClient(['погано', 'погано', 'погано', 'не має бути викликано'])
    out = generate([RECORD], [], client, ledger)
    assert len(client.prompts) == 3
    assert all((q.status, q.text) == ('rejected', '') for q in out)


def test_generate_missing_or_non_string_value_is_a_failed_attempt(outside_dir):
    client = FakeClient([{'same': OK_SAME, 'syn': 5, 'desc': None}, ALL_OK])
    out = _by_level(generate([RECORD], [], client, _ledger(outside_dir)))
    assert len(client.prompts) == 2 and all(q.status == 'ok' for q in out.values())


def test_generate_accepts_json_in_code_fence(outside_dir):
    fenced = '```json\n' + json.dumps(ALL_OK, ensure_ascii=False) + '\n```'
    out = generate([RECORD], [], FakeClient([fenced]), _ledger(outside_dir))
    assert all(q.status == 'ok' for q in out)


def test_generate_names_are_sent_and_not_counted(outside_dir):
    record = rec('r2', 'facts', 'Марія ховає ключ у бляшанці')
    client = FakeClient([{'same': 'Марія ключ', 'syn': 'x', 'desc': 'y'}] * 3)
    out = _by_level(generate([record], ['Марія'], client, _ledger(outside_dir)))
    assert out['same'].status == 'rejected'  # one content word is shared, the name does not count
    assert 'Марія' in client.prompts[0] and record.text in client.prompts[0]
    assert PROMPT in client.prompts[0] and 'facts' in client.prompts[0]


def test_generate_checks_budget_before_each_call(outside_dir):
    ledger = _ledger(outside_dir, cap=0.0)
    client = FakeClient([ALL_OK])
    with pytest.raises(BudgetExceeded):
        generate([RECORD], [], client, ledger)
    assert client.prompts == [] and ledger.usage('anthropic')['calls'] == 0


def test_generate_is_per_record_in_order(outside_dir):
    r2 = rec('r2', 'facts', 'Маяк стоїть на високій скелі')
    second = {'same': 'Маяк на високій скелі', 'syn': 'Чим відмикають замок', 'desc': OK_DESC}
    out = generate([RECORD, r2], [], FakeClient([ALL_OK, second]), _ledger(outside_dir))
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

def _args(outside_dir, **over):
    base = {'--data': str(outside_dir / 'data'), '--story': 'abc', '--out': str(outside_dir / 'out'),
            '--manifest': str(outside_dir / 'manifest.json'), '--cloud-stories': 'abc',
            '--spend-ledger': str(outside_dir / 'spend.json'), '--env-file': str(outside_dir / 'env')}
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


def _env(outside_dir, text='ANTHROPIC_API_KEY=k\n'):
    (outside_dir / 'env').write_text(text, encoding='utf-8')


def test_cli_inside_repo_first(outside_dir, capsys, forbid_client, monkeypatch):
    monkeypatch.setattr(cli, 'load_story', lambda args: pytest.fail('story loaded'))
    out = ROOT / 'tests' / 'retrieval_bench' / 'no_such_out'
    code, res = _run(capsys, _args(outside_dir, **{'--out': str(out)}))
    assert (code, res) == (2, {'error': 'inside_repo'}) and not out.exists()


def test_cli_story_errors_pass_through(outside_dir, capsys, forbid_client, monkeypatch):
    def fail(args):
        raise cli.BenchError('live_data')
    monkeypatch.setattr(cli, 'load_story', fail)
    assert _run(capsys, _args(outside_dir))[1] == {'error': 'live_data'}


def test_cli_cloud_not_allowed(outside_dir, capsys, forbid_client, story):
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    code, res = _run(capsys, _args(outside_dir, **{'--cloud-stories': 'zzz,'}))
    assert (code, res) == (2, {'error': 'cloud_not_allowed'})
    assert _run(capsys, _args(outside_dir, **{'--cloud-stories': ''}))[1] == {'error': 'cloud_not_allowed'}


def test_cli_ledger_missing_and_key_missing(outside_dir, capsys, forbid_client, story):
    _env(outside_dir)
    assert _run(capsys, _args(outside_dir))[1] == {'error': 'spend_ledger_missing'}
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    _env(outside_dir, '# nothing\nANTHROPIC_API_KEY=\n')
    assert _run(capsys, _args(outside_dir))[1] == {'error': 'anthropic_key_missing'}
    (outside_dir / 'env').unlink()
    assert _run(capsys, _args(outside_dir))[1] == {'error': 'anthropic_key_missing'}


def test_cli_exhausted_ledger_refuses_before_client(outside_dir, capsys, forbid_client, story):
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True).record('anthropic', 6.0, 1, 1)
    assert _run(capsys, _args(outside_dir))[1] == {'error': 'cloud_budget_exceeded'}


def test_cli_init_spend_ledger(outside_dir, capsys, forbid_client):
    p = outside_dir / 'sub' / 'spend.json'
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


def test_cli_happy_path_writes_outputs(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir, 'export ANTHROPIC_API_KEY="k-not-real"\n')
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    keys = []
    monkeypatch.setattr(cli, 'make_client', lambda key: keys.append(key) or SmartClient())
    code, res = _run(capsys, _args(outside_dir, **{'--n': '4', '--owner-k': '3'}))
    assert code == 0 and keys == ['k-not-real']
    assert res['targets'] == 4 and res['queries_ok']['syn'] == res['queries_ok']['desc'] == 4
    # a record with a single content word can never give two shared words: its "same" is rejected after 3 attempts
    assert all(res['queries_ok'][lv] + res['rejected'][lv] == 4 for lv in LEVELS)
    assert res['queries_ok']['same'] >= 3 and res['rejected']['syn'] == res['rejected']['desc'] == 0
    rejected_same = res['rejected']['same']
    assert res['usd_spent'] == pytest.approx((4 + 2 * rejected_same) * (800 * PRICE_IN + 80 * PRICE_OUT) / 1e6, abs=1e-6)
    assert 'k-not-real' not in json.dumps(res)
    data = json.loads((outside_dir / 'out' / 'set.json').read_text(encoding='utf-8'))
    meta = data['meta']
    assert meta['story'] == 'abc-story-id' and meta['model'] == HAIKU and meta['prompt_id'] == PROMPT_ID
    assert {'seed', 'n', 'levels'} <= set(meta) and meta['levels'] == list(LEVELS) and meta['owner_k'] == 3
    queries = [Query(**q) for q in data['queries']]
    assert len(queries) == 12 and all(q.text and q.record_sha256 for q in queries)
    snapshot = snapshot_hash(manifest(queries, meta))
    assert res['snapshot'] == snapshot
    mani = json.loads((outside_dir / 'manifest.json').read_text(encoding='utf-8'))
    assert mani == {**manifest(queries, meta), 'snapshot': snapshot}
    assert not any(q.text in json.dumps(mani, ensure_ascii=False) for q in queries)
    owner_path = outside_dir / 'out' / 'owner-check.json'
    owner = json.loads(owner_path.read_text(encoding='utf-8'))
    assert owner['snapshot'] == snapshot and len(owner['items']) == 3
    assert check_owner_file(owner_path, queries, snapshot, expected=3)[0] == 'owner_check_missing'  # verdicts pending
    assert SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}).usage('anthropic')['calls'] == 4 + 2 * rejected_same


def test_cli_exceptions_hide_texts(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir, 'ANTHROPIC_API_KEY=secret-key\n')
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)

    class Broken:
        def complete(self, prompt):
            raise RuntimeError('secret-key ' + prompt)
    monkeypatch.setattr(cli, 'make_client', lambda key: Broken())
    code, res = _run(capsys, _args(outside_dir, **{'--n': '2'}))
    assert (code, res) == (2, {'error': 'anthropic_call_failed', 'usd_spent': 0, 'records_done': 0})
    assert not (outside_dir / 'out' / 'set.json').exists()


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


def test_cli_rerun_after_failure_pays_only_for_unfinished_records(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    failing = CountingClient(fail_on=3)
    monkeypatch.setattr(cli, 'make_client', lambda key: failing)
    code, res = _run(capsys, _args(outside_dir, **{'--n': '5'}))
    assert code == 2 and res['error'] == 'anthropic_call_failed' and res['records_done'] == 2
    assert res['usd_spent'] > 0 and set(res) == {'error', 'usd_spent', 'records_done'}
    assert not (outside_dir / 'out' / 'set.json').exists() and (outside_dir / 'out' / 'gen-cache.json').is_file()
    spent_first = SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}).spent('anthropic')
    assert res['usd_spent'] == pytest.approx(spent_first)
    working = CountingClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: working)
    code, res = _run(capsys, _args(outside_dir, **{'--n': '5'}))
    assert code == 0 and res['targets'] == 5
    assert working.records == failing.records[2:] + [r for r in working.records if r not in failing.records]
    assert len(working.records) == 3 and not set(working.records[:1]) & set(failing.records[:2])
    data = json.loads((outside_dir / 'out' / 'set.json').read_text(encoding='utf-8'))
    assert len(data['queries']) == 15 and all(q['text'] for q in data['queries'])
    assert res['usd_spent'] == pytest.approx(
        SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}).spent('anthropic') - spent_first, abs=1e-6)
    third = CountingClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: third)
    code, res = _run(capsys, _args(outside_dir, **{'--n': '5'}))
    assert code == 0 and third.records == [] and res['usd_spent'] == 0


def test_cli_cache_is_keyed_by_record_prompt_and_model(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    monkeypatch.setattr(cli, 'make_client', lambda key: SmartClient())
    _run(capsys, _args(outside_dir, **{'--n': '2'}))
    entries = json.loads((outside_dir / 'out' / 'gen-cache.json').read_text(encoding='utf-8'))['entries']
    assert len(entries) == 2 and all(k.endswith(f'|{PROMPT_ID}|{HAIKU}') for k in entries)
    assert all(v['attempts'] >= 1 and len(v['queries']) == 3 for v in entries.values())
    monkeypatch.setattr(cli, 'PROMPT_ID', 'other-prompt')
    again = CountingClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: again)
    _run(capsys, _args(outside_dir, **{'--n': '2'}))
    assert len(again.records) == 2


def test_cli_budget_stop_reports_progress(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    monkeypatch.setattr(cli, 'make_client', lambda key: SmartClient())
    code, res = _run(capsys, _args(outside_dir, **{'--n': '3', '--anthropic-max-usd': '0.0004'}))
    assert code == 2 and res['error'] == 'cloud_budget_exceeded' and res['records_done'] < 3 and 'usd_spent' in res


def test_cli_ledger_corrupted_mid_run_is_spend_ledger_missing(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)

    class Corrupting(SmartClient):
        def complete(self, prompt):
            reply = super().complete(prompt)
            (outside_dir / 'spend.json').write_text('{bad', encoding='utf-8')
            return reply
    monkeypatch.setattr(cli, 'make_client', lambda key: Corrupting())
    code, res = _run(capsys, _args(outside_dir, **{'--n': '2'}))
    assert code == 2 and res['error'] == 'spend_ledger_missing' and res['records_done'] == 0


@pytest.mark.parametrize('message,code', [('live_data: refusing', 'live_data'), ('not_a_data_copy: x', 'not_a_data_copy'),
                                          ('C:/Users/someone/data does not exist', 'data_invalid'), ('', 'data_invalid')])
def test_data_error_codes_are_allowlisted(outside_dir, monkeypatch, message, code):
    import storygen.application.workspace_bench as wb

    def refuse(path, require):
        raise ValueError(message)
    monkeypatch.setattr(wb, '_check_data_dir', refuse)
    with pytest.raises(cli.BenchError) as error:
        cli.load_story(type('A', (), {'data': str(outside_dir), 'story': 'x'})())
    assert str(error.value) == code


# ---- F9: a name form in syn / desc fails the attempt ----------------------------------------------------------------

def test_generate_name_in_syn_or_desc_fails_the_attempt(outside_dir):
    client = FakeClient([{'same': OK_SAME, 'syn': 'Остапові відмикають замок', 'desc': 'Металева коробка Остапа'},
                         {'same': 'x', 'syn': OK_SYN, 'desc': OK_DESC}])
    out = _by_level(generate([RECORD], ['Остап Гнатюк'], client, _ledger(outside_dir)))
    assert len(client.prompts) == 2
    assert (out['syn'].text, out['desc'].text) == (OK_SYN, OK_DESC) and out['same'].text == OK_SAME
    client = FakeClient([{'same': OK_SAME, 'syn': 'Гнатюк відмикає замок', 'desc': OK_DESC}] * 3)
    out = _by_level(generate([RECORD], ['Остап Гнатюк'], client, _ledger(outside_dir)))
    assert out['syn'].status == 'rejected' and out['syn'].text == 'Гнатюк відмикає замок' and len(client.prompts) == 3


# ---- F10: truncated replies -----------------------------------------------------------------------------------------

def test_anthropic_client_exposes_stop_reason(monkeypatch):
    pytest.importorskip('anthropic')
    from memory_bench.paraphrase_gen import AnthropicClient
    client = AnthropicClient('test-key-not-real')

    class Usage:
        input_tokens, output_tokens = 3, 4

    def reply(**extra):
        return type('Reply', (), {'content': [], 'usage': Usage(), **extra})()
    replies = [reply(stop_reason='max_tokens'), reply()]
    monkeypatch.setattr(client, '_client', type('C', (), {'messages': type('M', (), {'create': lambda self, **kw: replies.pop(0)})()})())
    assert client.last_stop_reason is None
    client.complete('a')
    assert client.last_stop_reason == 'max_tokens'
    client.complete('b')  # a reply without the attribute
    assert client.last_stop_reason is None


class TruncatingClient(SmartClient):
    """Every second call stops on max_tokens."""

    def __init__(self):
        self.calls = 0
        self.last_stop_reason = None

    def complete(self, prompt):
        self.calls += 1
        self.last_stop_reason = 'max_tokens' if self.calls % 2 == 0 else 'end_turn'
        return super().complete(prompt)


def test_cli_counts_truncated_replies(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    client = TruncatingClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: client)
    code, res = _run(capsys, _args(outside_dir, **{'--n': '4'}))
    assert code == 0 and res['truncated'] == client.calls // 2 and client.calls >= 4


# ---- F11: estimate per call -----------------------------------------------------------------------------------------

def test_cli_reports_estimate_per_call_and_prices_date(outside_dir, capsys, monkeypatch, story):
    from memory_bench.paraphrase import FRAME_PARAMS, sample_targets, sampling_frame, story_names
    from memory_bench.paraphrase_gen import PRICES_DATE, _estimate_usd, build_prompt
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    monkeypatch.setattr(cli, 'make_client', lambda key: SmartClient())
    code, res = _run(capsys, _args(outside_dir, **{'--n': '4'}))
    targets = sample_targets(sampling_frame([story], FRAME_PARAMS), story.number, 4, 0)
    prompts = [build_prompt(r, story_names([story])) for r in targets]
    assert code == 0 and res['prices_date'] == PRICES_DATE and res['truncated'] == 0
    assert res['est_usd_per_call'] == pytest.approx(sum(_estimate_usd(p) for p in prompts) / len(prompts), abs=1e-8)  # rounded to 8 decimals


# ---- F1: a rerun keeps the owner's verdicts -------------------------------------------------------------------------

def _verdicts(path):
    return [i['verdict'] for i in json.loads(path.read_text(encoding='utf-8'))['items']]


def test_cli_rerun_keeps_owner_verdicts(outside_dir, capsys, monkeypatch, story):
    from memory_bench.paraphrase import set_verdict
    _env(outside_dir)
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    monkeypatch.setattr(cli, 'make_client', lambda key: SmartClient())
    code, first = _run(capsys, _args(outside_dir, **{'--n': '4'}))
    owner = outside_dir / 'out' / 'owner-check.json'
    assert code == 0 and first['owner_file'] == 'written'
    count = len(_verdicts(owner))
    for i in range(count):
        set_verdict(owner, i, 'yes' if i else 'no')
    before = owner.read_bytes()
    code, again = _run(capsys, _args(outside_dir, **{'--n': '4'}))  # from the cache: same snapshot
    assert code == 0 and again['snapshot'] == first['snapshot'] and again['owner_file'] == 'kept'
    assert owner.read_bytes() == before
    # another snapshot (another seed): the old file is moved aside with its verdicts, a new one is written
    code, other = _run(capsys, _args(outside_dir, **{'--n': '4', '--seed': '7'}))
    assert code == 0 and other['snapshot'] != first['snapshot'] and other['owner_file'] == 'rotated'
    moved = outside_dir / 'out' / f"owner-check.{first['snapshot'][:8]}.json"
    assert moved.read_bytes() == before and set(_verdicts(owner)) == {None}
    owner.write_text('{bad', encoding='utf-8')  # unreadable: simply written anew
    code, last = _run(capsys, _args(outside_dir, **{'--n': '4', '--seed': '7'}))
    assert code == 0 and last['owner_file'] == 'written' and set(_verdicts(owner)) == {None}
