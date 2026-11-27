import json

import pytest

np = pytest.importorskip('numpy')
httpx = pytest.importorskip('httpx')

from memory_bench.cloud_spend import BudgetExceeded, SpendLedger  # noqa: E402
from memory_bench.embeddings import MODELS, CachedEmbedder, VoyageEmbedder, cloud_allowed  # noqa: E402

KEY = 'SECRET-KEY'
DIM = 4


@pytest.fixture
def ledger(outside_dir):
    return SpendLedger.open(outside_dir / 'spend.json', {'voyage': 1.0}, create=True)


def _vector(text):
    return [float(len(text)), 1.0, 0.0, 2.0]


def ok_handler(seen=None, tokens_per_text=3, reverse=False):
    def handler(request):
        body = json.loads(request.content)
        if seen is not None:
            seen.append(request)
        data = [{'object': 'embedding', 'embedding': _vector(t), 'index': i} for i, t in enumerate(body['input'])]
        if reverse:
            data = list(reversed(data))
        return httpx.Response(200, json={'object': 'list', 'data': data, 'model': 'voyage-4',
                                         'usage': {'total_tokens': tokens_per_text * len(data)}})
    return handler


def make(handler, ledger, sleeps=None):
    return VoyageEmbedder('voyage-4', KEY, ledger, transport=httpx.MockTransport(handler),
                          sleep=(sleeps.append if sleeps is not None else (lambda s: None)), dim=DIM)


def test_models_entry():
    assert MODELS['voyage-4'] == {'kind': 'cloud', 'model_id': 'voyage-4', 'revision': 'atlas-1024', 'dim': 1024,
                                  'max_tokens': 32000}
    assert VoyageEmbedder.BATCH == 128 and VoyageEmbedder.PROVIDER == 'voyage' and VoyageEmbedder.PRICE_PER_MTOK == 0.06


def test_request_shape_and_input_type(ledger):
    seen = []
    emb = make(ok_handler(seen), ledger)
    emb.embed(['один', 'два'], 'passage')
    emb.embed(['план'], 'query')
    assert json.loads(seen[0].content) == {'input': ['один', 'два'], 'model': 'voyage-4', 'input_type': 'document'}
    assert json.loads(seen[1].content) == {'input': ['план'], 'model': 'voyage-4', 'input_type': 'query'}
    req = seen[0]
    assert req.method == 'POST' and str(req.url) == 'https://ai.mongodb.com/v1/embeddings'
    assert req.headers['authorization'] == f'Bearer {KEY}'
    assert emb.query_prefix == emb.passage_prefix == '' and emb.truncated == 0
    assert emb.last_truncated == [False] and emb.max_tokens == 32000 and emb.revision == 'atlas-1024'


def test_unknown_kind_raises_before_request(ledger, capsys):
    calls = []
    emb = make(lambda request: calls.append(request), ledger)
    with pytest.raises(ValueError) as info:
        emb.embed(['x'], 'other')
    assert str(info.value) == 'cloud_input_type' and calls == [] and capsys.readouterr().err == ''


def test_vectors_follow_index_and_are_normalized(ledger):
    emb = make(ok_handler(reverse=True), ledger)
    texts = ['a', 'bbb', 'cc']
    out = emb.embed(texts, 'passage')
    assert out.dtype == np.float32 and out.shape == (3, DIM)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0, atol=1e-6)
    expected = np.array([_vector(t) for t in texts], dtype=np.float32)
    expected /= np.linalg.norm(expected, axis=1, keepdims=True)
    assert np.allclose(out, expected, atol=1e-6)


def test_ledger_records_each_batch_and_estimate_printed(ledger, capsys):
    seen = []
    emb = make(ok_handler(seen, tokens_per_text=5), ledger)
    out = emb.embed([f't{i}' for i in range(130)], 'passage')
    assert out.shape == (130, DIM) and len(seen) == 2
    usage = ledger.usage('voyage')
    assert usage['calls'] == 2 and usage['input_tokens'] == 650 and usage['output_tokens'] == 0
    assert usage['usd'] == pytest.approx(650 * 0.06 / 1e6)
    on_disk = SpendLedger.open(ledger.path, {'voyage': 1.0}).usage('voyage')
    assert on_disk['calls'] == 2 and on_disk['usd'] == pytest.approx(650 * 0.06 / 1e6)
    assert emb.tokens == 650 and len(emb.latencies) == 2
    err = capsys.readouterr().err
    assert err.count('\n') == 1
    # ceil(len / 2): t0..t9 give 1 token each, t10..t129 give 2 each
    assert err.strip() == 'cloud_estimate provider=voyage tokens=250 usd=0.0000 spent_usd=0.0000 max_usd=1.0'
    assert KEY not in err and 't129' not in err


def test_estimate_printed_before_first_request(ledger, capsys):
    printed = []

    def handler(request):
        printed.append(capsys.readouterr().err)
        return ok_handler()(request)

    make(handler, ledger).embed(['x'], 'query')
    assert printed[0].startswith('cloud_estimate provider=voyage tokens=1 ')


def test_budget_refused_before_any_request(ledger, capsys):
    ledger.record('voyage', 0.999, 0, 0)
    calls = []
    emb = make(lambda request: calls.append(request), ledger)
    with pytest.raises(BudgetExceeded) as info:
        emb.embed(['а' * 100_000], 'passage')  # 50k tokens * 0.06 / 1e6 = 0.003 > 0.001 left
    assert str(info.value) == 'cloud_budget_exceeded' and calls == []
    assert capsys.readouterr().err.strip() == \
        'cloud_estimate provider=voyage tokens=50000 usd=0.0030 spent_usd=0.9990 max_usd=1.0'
    assert ledger.usage('voyage')['calls'] == 1


def test_429_retries_then_succeeds(ledger):
    statuses = iter([429, 429, 200])
    sleeps = []

    def handler(request):
        status = next(statuses)
        return ok_handler()(request) if status == 200 else httpx.Response(429, json={'detail': 'slow down'})

    out = make(handler, ledger, sleeps).embed(['x', 'y'], 'query')
    assert out.shape == (2, DIM) and sleeps == [1, 2] and ledger.usage('voyage')['calls'] == 1


def test_429_exhausted_gives_code(ledger):
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={'detail': 'slow down'})

    with pytest.raises(ValueError) as info:
        make(handler, ledger, sleeps).embed(['x'], 'query')
    assert str(info.value) == 'cloud_http_429' and len(calls) == 4 and sleeps == [1, 2, 4]
    assert ledger.usage('voyage')['calls'] == 0


def test_errors_never_echo_text_or_key(ledger):
    text = 'секретний текст'
    sleeps = []
    emb = make(lambda request: httpx.Response(500, json={'detail': f'{text} {KEY}'}), ledger, sleeps)
    with pytest.raises(ValueError) as info:
        emb.embed([text], 'passage')
    assert str(info.value) == 'cloud_http_500' and sleeps == []
    assert text not in repr(info.value) and KEY not in repr(info.value) and info.value.__cause__ is None


def test_transport_error_gives_code(ledger):
    def handler(request):
        raise httpx.ConnectError(f'boom {KEY}')

    with pytest.raises(ValueError) as info:
        make(handler, ledger).embed(['x'], 'query')
    assert str(info.value) == 'cloud_error' and KEY not in repr(info.value) and info.value.__cause__ is None


@pytest.mark.parametrize('body', [
    {'data': [{'embedding': [1.0, 0, 0, 0], 'index': 0}], 'usage': {}},
    {'data': [{'embedding': [1.0, 0, 0, 0], 'index': 0}]},
    {'data': [{'index': 0}], 'usage': {'total_tokens': 1}},
    {'data': [], 'usage': {'total_tokens': 1}},
    {'data': [{'embedding': [1.0, 0, 0, 0], 'index': 5}], 'usage': {'total_tokens': 1}},
    {'data': [{'embedding': [1.0, 0], 'index': 0}], 'usage': {'total_tokens': 1}},
    {'data': [{'embedding': ['a', 0, 0, 0], 'index': 0}], 'usage': {'total_tokens': 1}},
    {'data': None, 'usage': {'total_tokens': 1}},
    [],
])
def test_bad_response_code(ledger, body):
    emb = make(lambda request: httpx.Response(200, json=body), ledger)
    with pytest.raises(ValueError) as info:
        emb.embed(['секретний текст'], 'query')
    assert str(info.value) == 'cloud_bad_response' and info.value.__cause__ is None
    assert ledger.usage('voyage')['calls'] == 0


def test_non_json_body_is_bad_response(ledger):
    emb = make(lambda request: httpx.Response(200, content=b'not json'), ledger)
    with pytest.raises(ValueError, match='cloud_bad_response'):
        emb.embed(['x'], 'query')


def test_empty_input_makes_no_request_and_prints_nothing(ledger, capsys):
    def handler(request):
        raise AssertionError('no request expected')

    out = make(handler, ledger).embed([], 'query')
    assert out.shape == (0, DIM) and capsys.readouterr().err == ''


def test_client_has_timeout_and_close(ledger):
    emb = make(ok_handler(), ledger)
    assert emb._client.timeout.read == 60.0
    emb.close()
    assert emb._client.is_closed


def test_cloud_allowed_by_prefix_only():
    assert cloud_allowed('demo-1', ['demo-', 'x']) is True
    assert cloud_allowed('story-1', ['demo-']) is False
    assert cloud_allowed('demo-1', []) is False
    assert cloud_allowed('demo-1', ['']) is False
    assert cloud_allowed('demo-1', ('', 'demo')) is True


def test_partial_failure_keeps_paid_batches(outside_dir, ledger):
    texts = [f'текст {i}' for i in range(300)]
    seen = []
    good = ok_handler()

    def failing(request):
        seen.append(len(json.loads(request.content)['input']))
        return good(request) if len(seen) < 3 else httpx.Response(500, json={'detail': 'x'})

    cache = outside_dir / 'cache'
    cached = CachedEmbedder(make(failing, ledger), cache)
    with pytest.raises(ValueError) as info:
        cached.embed(texts, 'passage')
    assert str(info.value) == 'cloud_http_500' and seen == [128, 128, 44]
    assert len(list(cache.glob('*.npz'))) == 256 and not list(cache.glob('*.tmp'))
    assert ledger.usage('voyage')['calls'] == 2
    paid = ledger.usage('voyage')['usd']
    assert paid == pytest.approx(256 * 3 * 0.06 / 1e6)

    resent = []
    rerun = CachedEmbedder(make(ok_handler(resent), ledger), cache)
    out = rerun.embed(texts, 'passage')
    assert out.shape == (300, DIM) and [len(json.loads(r.content)['input']) for r in resent] == [44]
    assert json.loads(resent[0].content)['input'] == texts[256:]
    assert rerun.hits == 256 and rerun.misses == 44
    assert ledger.usage('voyage')['calls'] == 3
    assert len(list(cache.glob('*.npz'))) == 300
