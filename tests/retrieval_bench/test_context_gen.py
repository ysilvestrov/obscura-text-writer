import hashlib
import json
import os
import subprocess
import sys

import pytest

import rag_contexts as cli
from memory_bench.cloud_spend import SpendLedger
from memory_bench.context_gen import (CONTEXT_MAX_TOKENS, CONTEXT_PROMPT, CONTEXT_PROMPT_ID, build_context_prompt, context_key,
                                      context_snapshot, context_targets, generate_context)
from memory_bench.paraphrase import ROOT
from memory_bench.paraphrase_gen import HAIKU
from tests.retrieval_bench.helpers import rec, scene

SENTINEL = 'ЗЕБРАЗЕБРА'


class FakeClient:
    """Replies are (text, stop_reason) pairs; the last one repeats. Counts the calls."""

    def __init__(self, replies=(('Марія, біля моря, вранці.', 'end_turn'),)):
        self.replies, self.calls, self.last_stop_reason, self.prompts = list(replies), 0, None, []

    def complete(self, prompt):
        self.prompts.append(prompt)
        text, self.last_stop_reason = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return text, 1000, 100


def _ledger(outside_dir, cap=5.0):
    return SpendLedger.open(outside_dir / 'spend.json', {'anthropic': cap}, create=True)


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def test_constants_and_prompt():
    assert CONTEXT_PROMPT_ID == _sha(CONTEXT_PROMPT)
    assert CONTEXT_MAX_TOKENS == 4096
    assert CONTEXT_PROMPT.startswith("Нижче — сцена історії і один запис пам'яті") and CONTEXT_PROMPT.endswith('Відповідай лише текстом контексту.')
    prompt = build_context_prompt(rec('a', 'facts', 'Марія  в\nхалаті', scene=1), 'Проза сцени.')
    assert prompt == f'{CONTEXT_PROMPT}\n\nСцена:\nПроза сцени.\n\nЗапис: Марія в халаті'


def test_context_key_changes_with_prose_scene_text_and_claim():
    base = rec('a', 'facts', 'Марія в халаті', scene=1)
    key = context_key(base, 'проза')
    assert key == context_key(rec('a', 'facts', 'Марія в халаті', scene=1), 'проза')
    assert key == context_key(rec('a', 'states', 'Марія в халаті', scene=1), 'проза')  # category is not in the key
    assert key == _sha('|'.join((HAIKU, CONTEXT_PROMPT_ID, 'a', '1', _sha('Марія в халаті'), _sha('проза'))))
    others = {context_key(base, 'інша проза'), context_key(rec('a', 'facts', 'Марія в халаті', scene=2), 'проза'),
              context_key(rec('a', 'facts', 'Марія без халата', scene=1), 'проза'), context_key(rec('b', 'facts', 'Марія в халаті', scene=1), 'проза')}
    assert len(others | {key}) == 5


def test_targets_unique_and_no_source_counted():
    dup = rec('a', 'facts', 'Марія в халаті', scene=1)
    s1 = scene([dup, rec('b', 'facts', 'Остап вдома', scene=1), rec('t', 'timeline', 'Марія прийшла', scene=1)], number=1, prose='Проза 1')
    s2 = scene([dup, rec('c', 'facts', 'Без джерела', scene=None), rec('d', 'facts', 'Сцени немає', scene=7),
                rec('e', 'facts', 'Із першої', scene=1)], number=2, prose='Проза 2')
    targets, no_source = context_targets([s1, s2])
    assert [(r.claim_id, p) for r, p in targets] == [('a', 'Проза 1'), ('b', 'Проза 1'), ('e', 'Проза 1')]
    assert no_source == 2
    assert context_targets([s1, s2, s2]) == (targets, no_source)


def test_truncated_or_empty_reply_never_cached_and_retried(outside_dir):
    ledger, record = _ledger(outside_dir), rec('a', 'facts', 'Марія в халаті', scene=1)
    client = FakeClient([('обрізано…', 'max_tokens'), ('   ', 'end_turn'), ('  Контекст.  ', 'end_turn')])
    assert generate_context(record, 'проза', client, ledger) == ('Контекст.', 'ok')
    assert client.calls == 3 and ledger.usage('anthropic')['calls'] == 3
    client = FakeClient([('обрізано…', 'max_tokens'), ('', 'end_turn'), ('', 'end_turn')])
    assert generate_context(record, 'проза', client, ledger) == (None, 'empty')
    assert client.calls == 3 and ledger.usage('anthropic')['calls'] == 6
    client = FakeClient([('x', 'max_tokens')])
    assert generate_context(record, 'проза', client, ledger) == (None, 'truncated')


def test_budget_stops_before_call(outside_dir):
    ledger = _ledger(outside_dir, cap=0.001)
    ledger.record('anthropic', 0.001, 1, 1)
    client = FakeClient()
    assert generate_context(rec('a', 'facts', 'x', scene=1), 'проза', client, ledger) == (None, 'budget')
    assert client.calls == 0


# ---- CLI ----------------------------------------------------------------------------------------------------------

def _args(outside_dir, **over):
    base = {'--data': str(outside_dir / 'data'), '--story': 'abc', '--out': str(outside_dir / 'out'),
            '--manifest': str(outside_dir / 'manifest.json'), '--cloud-stories': 'abc',
            '--spend-ledger': str(outside_dir / 'spend.json'), '--env-file': str(outside_dir / 'env')}
    base.update(over)
    return [x for kv in base.items() for x in kv]


def _scenes(n=4):
    records = [rec(f'r{i}', 'facts', f'Запис номер {i} {SENTINEL}', scene=1) for i in range(n)]
    return [scene(records + [rec('t', 'timeline', 'Подія', scene=1)], number=1, prose=f'Проза {SENTINEL} сцени')]


@pytest.fixture
def forbid_client(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('client constructed')
    monkeypatch.setattr(cli, 'make_client', boom)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)


@pytest.fixture
def story(monkeypatch):
    scenes = _scenes()
    monkeypatch.setattr(cli, 'load_story', lambda args: ('abc-story-id', scenes))
    return scenes


def _run(capsys, argv):
    code = cli.main(argv)
    return code, json.loads(capsys.readouterr().out)


def _env(outside_dir, text='ANTHROPIC_API_KEY=k\n'):
    (outside_dir / 'env').write_text(text, encoding='utf-8')


def _contexts(outside_dir):
    return json.loads((outside_dir / 'out' / 'contexts.json').read_text(encoding='utf-8'))


def test_refusals_before_client(outside_dir, capsys, forbid_client, story, monkeypatch):
    _env(outside_dir)
    inside = ROOT / 'tests' / 'retrieval_bench' / 'no_such_out'
    assert _run(capsys, _args(outside_dir, **{'--out': str(inside)})) == (2, {'error': 'inside_repo'}) and not inside.exists()
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    assert _run(capsys, _args(outside_dir, **{'--cloud-stories': 'zzz'})) == (2, {'error': 'cloud_not_allowed'})
    (outside_dir / 'spend.json').unlink()
    assert _run(capsys, _args(outside_dir)) == (2, {'error': 'spend_ledger_missing'})
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}, create=True)
    _env(outside_dir, 'ANTHROPIC_API_KEY=\n')
    assert _run(capsys, _args(outside_dir)) == (2, {'error': 'anthropic_key_missing'})
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}).record('anthropic', 6.0, 1, 1)
    _env(outside_dir)
    assert _run(capsys, _args(outside_dir)) == (2, {'error': 'cloud_budget_exceeded'})

    def fail(args):
        raise cli.BenchError('live_data')
    monkeypatch.setattr(cli, 'load_story', fail)
    assert _run(capsys, _args(outside_dir)) == (2, {'error': 'live_data'})


def test_happy_path_cache_and_snapshot(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    _ledger(outside_dir)
    client = FakeClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: client)
    code, res = _run(capsys, _args(outside_dir))
    assert code == 0 and client.calls == 4
    assert (res['targets'], res['ok'], res['failed'], res['truncated'], res['no_source'], res['cached']) == (4, 4, 0, 0, 0, 0)
    assert res['prices_date'] == '2026-11-27' and res['est_usd_per_call'] > 0 and res['usd_spent'] > 0
    data = _contexts(outside_dir)
    assert data['meta']['model'] == HAIKU and data['meta']['prompt_id'] == CONTEXT_PROMPT_ID and data['meta']['story'] == 'abc-story-id'
    assert len(data['items']) == 4 and all(i['status'] == 'ok' and i['context'] for i in data['items'].values())
    assert data['snapshot'] == res['snapshot'] == context_snapshot(data['items'])
    pairs = sorted([k, i['status']] for k, i in data['items'].items())
    assert data['snapshot'] == _sha(json.dumps(pairs))
    # a rerun takes everything from the cache
    code, res = _run(capsys, _args(outside_dir))
    assert code == 0 and client.calls == 4 and (res['cached'], res['ok'], res['usd_spent']) == (4, 4, 0)


def test_three_failures_give_failed_and_rerun_pays_only_failed(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    _ledger(outside_dir)

    class Picky(FakeClient):
        def complete(self, prompt):
            self.calls += 1
            if 'номер 1 ' in prompt:
                self.last_stop_reason = 'max_tokens'
                return 'обрізано', 10, 10
            self.last_stop_reason = 'end_turn'
            return 'Контекст.', 10, 10
    client = Picky()
    monkeypatch.setattr(cli, 'make_client', lambda key: client)
    code, res = _run(capsys, _args(outside_dir))
    assert code == 0 and (res['ok'], res['failed'], res['truncated'], client.calls) == (3, 1, 3, 6)
    failed = [i for i in _contexts(outside_dir)['items'].values() if i['status'] == 'failed']
    assert len(failed) == 1 and 'context' not in failed[0]
    good = FakeClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: good)
    code, res = _run(capsys, _args(outside_dir))
    assert code == 0 and good.calls == 1 and (res['ok'], res['failed'], res['cached']) == (4, 0, 3)
    assert all(i['status'] == 'ok' for i in _contexts(outside_dir)['items'].values())


def test_truncated_counter_counts_cut_attempts_only(outside_dir, capsys, monkeypatch):
    monkeypatch.setattr(cli, 'load_story', lambda args: ('abc', _scenes(1)))
    _env(outside_dir)
    _ledger(outside_dir)
    client = FakeClient([('…', 'max_tokens'), ('', 'end_turn'), ('Контекст.', 'end_turn')])
    monkeypatch.setattr(cli, 'make_client', lambda key: client)
    code, res = _run(capsys, _args(outside_dir))
    assert code == 0 and (res['truncated'], res['ok'], res['failed'], client.calls) == (1, 1, 0, 3)
    assert SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 5.0}).usage('anthropic')['calls'] == 3


def test_budget_stop_saves_paid_work_and_exits(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    # each call costs 0.00015 and is estimated at ~0.0005; the cap fits one call with its margin but not two
    SpendLedger.open(outside_dir / 'spend.json', {'anthropic': 0.0006}, create=True)
    client = FakeClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: client)
    code, res = _run(capsys, _args(outside_dir, **{'--anthropic-max-usd': '0.0006'}))
    assert code == 2 and res == {'error': 'cloud_budget_exceeded'} and client.calls == 1
    data = _contexts(outside_dir)
    assert len(data['items']) == client.calls and data['snapshot'] == context_snapshot(data['items'])
    assert not (outside_dir / 'manifest.json').exists()


def test_stop_before_cached_ok_records_keeps_them(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    _ledger(outside_dir)

    class FailFirst(FakeClient):
        def complete(self, prompt):
            self.calls += 1
            self.last_stop_reason = 'max_tokens' if 'номер 0 ' in prompt else 'end_turn'
            return 'Контекст ' + str(len(self.prompts)), 10, 10
    monkeypatch.setattr(cli, 'make_client', lambda key: FailFirst())
    assert _run(capsys, _args(outside_dir))[1]['failed'] == 1  # r0 failed; r1..r3 ok and come after it
    before = _contexts(outside_dir)['items']
    ok_before = {k: v for k, v in before.items() if v['status'] == 'ok'}
    assert len(ok_before) == 3 and before[next(k for k, v in before.items() if v['claim_id'] == 'r0')]['status'] == 'failed'

    class Boom(FakeClient):
        def complete(self, prompt):
            raise RuntimeError(SENTINEL)
    monkeypatch.setattr(cli, 'make_client', lambda key: Boom())
    code, res = _run(capsys, _args(outside_dir))
    assert code == 2 and res['error'] == 'anthropic_call_failed'
    after = _contexts(outside_dir)['items']
    assert {k: v for k, v in after.items() if v['status'] == 'ok'} == ok_before  # unreached ok contexts survive
    good = FakeClient()
    monkeypatch.setattr(cli, 'make_client', lambda key: good)
    code, res = _run(capsys, _args(outside_dir))
    assert code == 0 and good.calls == 1 and (res['ok'], res['failed'], res['cached']) == (4, 0, 3)


def test_output_and_manifest_carry_no_text(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    _ledger(outside_dir)
    monkeypatch.setattr(cli, 'make_client', lambda key: FakeClient([(f'Контекст {SENTINEL}', 'end_turn')]))
    cli.main(_args(outside_dir))
    out = capsys.readouterr().out
    manifest_raw = (outside_dir / 'manifest.json').read_text(encoding='utf-8')
    assert SENTINEL not in out and SENTINEL not in manifest_raw and 'Запис номер' not in manifest_raw
    mani = json.loads(manifest_raw)
    assert set(mani) == {'meta', 'snapshot', 'items'} and mani['snapshot'] == json.loads(out)['snapshot']
    assert all(set(i) == {'claim_id', 'source_scene', 'status'} for i in mani['items'].values()) and len(mani['items']) == 4
    assert SENTINEL in (outside_dir / 'out' / 'contexts.json').read_text(encoding='utf-8')  # texts live outside the repo only


def test_client_exception_hides_text_and_saves_progress(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    _ledger(outside_dir)

    class Boom(FakeClient):
        def complete(self, prompt):
            if self.calls == 2:
                raise RuntimeError(SENTINEL)
            return super().complete(prompt)
    monkeypatch.setattr(cli, 'make_client', lambda key: Boom())
    code = cli.main(_args(outside_dir))
    out = capsys.readouterr().out
    assert code == 2 and SENTINEL not in out and json.loads(out)['error'] == 'anthropic_call_failed'
    assert len(_contexts(outside_dir)['items']) == 2


def test_modules_import_without_numpy_and_anthropic():
    code = ("import sys; sys.modules['numpy']=None; sys.modules['anthropic']=None; "
            "import rag_contexts, memory_bench.context_gen")
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(ROOT / 'scripts'), str(ROOT / 'src')])}
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=ROOT, env=env)
    assert r.returncode == 0, r.stderr


def test_anthropic_client_max_tokens_param(monkeypatch):
    pytest.importorskip('anthropic')
    from memory_bench.paraphrase_gen import MAX_TOKENS, AnthropicClient
    seen = []

    class Usage:
        input_tokens, output_tokens = 1, 1
    reply = type('R', (), {'content': [], 'usage': Usage()})()
    for kwargs, expected in (({}, MAX_TOKENS), ({'max_tokens': CONTEXT_MAX_TOKENS}, 4096), ({'max_tokens': 77}, 77)):
        client = AnthropicClient('test-key-not-real', **kwargs)
        monkeypatch.setattr(client, '_client', type('C', (), {'messages': type('M', (), {'create': lambda self, **kw: seen.append(kw) or reply})()})())
        client.complete('x')
        assert seen[-1]['max_tokens'] == expected


# ---- final review fixes ---------------------------------------------------------------------------------------------

def test_refusal_and_other_stop_reasons_fail_the_attempt(outside_dir):
    ledger, record = _ledger(outside_dir), rec('a', 'facts', 'Марія в халаті', scene=1)
    client = FakeClient([('Не можу цього зробити, але ось контекст.', 'refusal'), ('частково', 'pause_turn'), ('Контекст.', 'end_turn')])
    assert generate_context(record, 'проза', client, ledger) == ('Контекст.', 'ok')
    assert client.calls == 3 and ledger.usage('anthropic')['calls'] == 3
    assert generate_context(record, 'проза', FakeClient([('текст відмови', 'refusal')]), ledger) == (None, 'refusal')
    assert generate_context(record, 'проза', FakeClient([('текст', 'stop_sequence')]), ledger) == (None, 'stop_stop_sequence')
    assert generate_context(record, 'проза', FakeClient([('текст', None)]), ledger) == ('текст', 'ok')  # fake clients without the attribute


def test_refusal_and_duplicate_counters_without_text(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    _ledger(outside_dir)

    class Refusing(FakeClient):
        def complete(self, prompt):
            self.calls += 1
            if 'номер 1 ' in prompt:
                self.last_stop_reason = 'refusal'
                return 'ВІДМОВА-ТЕКСТ', 10, 10
            self.last_stop_reason = 'end_turn'
            return 'Однаковий контекст.', 10, 10
    client = Refusing()
    monkeypatch.setattr(cli, 'make_client', lambda key: client)
    code, res = _run(capsys, _args(outside_dir))
    assert code == 0 and (res['ok'], res['failed'], res['refusal'], res['truncated'], client.calls) == (3, 1, 3, 0, 6)
    assert res['duplicate_contexts'] == 3
    assert 'ВІДМОВА-ТЕКСТ' not in json.dumps(_contexts(outside_dir)) and 'Однаковий' not in json.dumps(res)


def test_duplicate_counter_zero_for_distinct_contexts(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    _ledger(outside_dir)

    class Distinct(FakeClient):
        def complete(self, prompt):
            self.calls += 1
            self.last_stop_reason = 'end_turn'
            return f'Контекст {self.calls}.', 10, 10
    monkeypatch.setattr(cli, 'make_client', lambda key: Distinct())
    code, res = _run(capsys, _args(outside_dir))
    assert code == 0 and res['duplicate_contexts'] == 0 and res['refusal'] == 0


def test_forecast_line_on_stderr_before_first_call(outside_dir, capsys, monkeypatch, story):
    _env(outside_dir)
    _ledger(outside_dir)
    order = []

    class Spy(FakeClient):
        def complete(self, prompt):
            order.append(capsys.readouterr().err)
            return super().complete(prompt)
    monkeypatch.setattr(cli, 'make_client', lambda key: Spy())
    code = cli.main(_args(outside_dir))
    err = order[0]
    assert code == 0
    line = [x for x in err.splitlines() if x.startswith('context_forecast')]
    assert len(line) == 1 and line[0].startswith('context_forecast calls=4 est_usd=')
    assert 'spent_usd=0.0000' in line[0] and 'max_usd=5.0' in line[0] and SENTINEL not in err
