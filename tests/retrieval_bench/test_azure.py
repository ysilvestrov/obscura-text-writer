import json

import pytest

np = pytest.importorskip('numpy')
httpx = pytest.importorskip('httpx')

from memory_bench.embeddings import AzureEmbedder, cloud_allowed


def make(handler, **kw):
    args = dict(key='azure-3-large', endpoint='https://example.openai.azure.com', api_key='SECRET-KEY',
                deployment='emb', api_version='2024-02-01', price_per_mtok=0.13, max_usd=1.0)
    args.update(kw)
    return AzureEmbedder(transport=httpx.MockTransport(handler), **args)


def test_azure_refuses_over_budget():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    emb = make(handler, price_per_mtok=1.0, max_usd=0.0001)
    with pytest.raises(ValueError, match='cloud_budget'):
        emb.embed(['а' * 1000, 'б' * 1000], 'passage')  # 1000 tokens * 1 / 1e6 = 0.001 > 0.0001
    assert calls == [] and emb.tokens == 0 and emb.usd == 0


def test_azure_parses_embeddings_and_counts_usage():
    seen = []

    def handler(request):
        seen.append(request)
        body = json.loads(request.content)
        data = [{'index': i, 'embedding': [3.0 * (i + 1), 4.0 * (i + 1)]} for i in range(len(body['input']))]
        return httpx.Response(200, json={'data': list(reversed(data)), 'usage': {'prompt_tokens': 10 * len(data)}})

    emb = make(handler)
    out = emb.embed(['один', 'два', 'три'], 'query')
    assert out.dtype == np.float32 and out.shape == (3, 2)
    assert np.allclose(out, [[0.6, 0.8]] * 3, atol=1e-6)
    assert emb.tokens == 30 and emb.usd == pytest.approx(30 * 0.13 / 1e6)
    assert len(emb.latencies) == 1 and emb.last_truncated == [False] * 3 and emb.truncated == 0
    req = seen[0]
    assert req.headers['api-key'] == 'SECRET-KEY'
    assert req.url.path == '/openai/deployments/emb/embeddings' and req.url.params['api-version'] == '2024-02-01'
    assert json.loads(req.content) == {'input': ['один', 'два', 'три']}


def test_azure_batches_and_keeps_order():
    def handler(request):
        body = json.loads(request.content)
        data = [{'index': i, 'embedding': [float(len(t)), 1.0]} for i, t in enumerate(body['input'])]
        return httpx.Response(200, json={'data': data, 'usage': {'prompt_tokens': len(data)}})

    emb = make(handler)
    out = emb.embed(['x' * (i + 1) for i in range(150)], 'passage')
    assert out.shape == (150, 2) and len(emb.latencies) == 3 and emb.tokens == 150
    assert np.argmax(out[:, 0]) == 149 and np.argmin(out[:, 0]) == 0


def test_azure_http_error_leaks_nothing():
    emb = make(lambda request: httpx.Response(401, json={'error': 'SECRET-KEY denied'}))
    with pytest.raises(ValueError) as info:
        emb.embed(['секретний текст'], 'query')
    assert str(info.value) == 'cloud_http_401'
    assert 'SECRET' not in repr(info.value) and 'секретний' not in repr(info.value)


def test_azure_empty_input_makes_no_request():
    def handler(request):
        raise AssertionError('no request expected')

    assert make(handler).embed([], 'query').shape[0] == 0


def test_cloud_allowed_by_prefix_only():
    assert cloud_allowed('demo-1', ['demo-', 'x']) is True
    assert cloud_allowed('story-1', ['demo-']) is False
    assert cloud_allowed('demo-1', []) is False
    assert cloud_allowed('demo-1', ['']) is False
    assert cloud_allowed('demo-1', ('', 'demo')) is True
