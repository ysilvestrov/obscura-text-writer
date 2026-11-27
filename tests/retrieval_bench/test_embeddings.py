import tempfile
from pathlib import Path

import pytest

np = pytest.importorskip('numpy')

from memory_bench.embeddings import ROOT, CachedEmbedder, FakeEmbedder, MODELS, TruncatedEmbedder  # noqa: E402


class CountingEmbedder(FakeEmbedder):
    def __init__(self, revision='r1', query_prefix='', passage_prefix=''):
        super().__init__()
        self.revision = revision
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self.calls = []

    def embed(self, texts, kind):
        self.calls.append((tuple(texts), kind))
        return super().embed(texts, kind)


def test_fake_embedder_is_deterministic_and_normalized():
    e = FakeEmbedder(dim=16)
    a = e.embed(['alpha', 'beta'], 'passage')
    b = FakeEmbedder(dim=16).embed(['alpha', 'beta'], 'passage')
    assert a.dtype == np.float32 and a.shape == (2, 16)
    assert np.array_equal(a, b)
    assert not np.array_equal(a[0], a[1])
    assert np.allclose(np.linalg.norm(a, axis=1), 1.0, atol=1e-6)


def test_cache_hit_skips_inner():
    with tempfile.TemporaryDirectory() as d:
        inner = CountingEmbedder()
        cached = CachedEmbedder(inner, Path(d))
        first = cached.embed(['a', 'b'], 'passage')
        assert (cached.hits, cached.misses) == (0, 2)
        second = cached.embed(['b', 'a'], 'passage')
        assert (cached.hits, cached.misses) == (2, 2)
        assert len(inner.calls) == 1
        assert np.array_equal(second, first[::-1])
        again = CachedEmbedder(CountingEmbedder(), Path(d))
        again.embed(['a'], 'passage')
        assert (again.hits, again.misses) == (1, 0)


def test_cache_key_includes_revision():
    with tempfile.TemporaryDirectory() as d:
        CachedEmbedder(CountingEmbedder(revision='r1'), Path(d)).embed(['a'], 'passage')
        other = CachedEmbedder(CountingEmbedder(revision='r2'), Path(d))
        other.embed(['a'], 'passage')
        assert (other.hits, other.misses) == (0, 1)


def test_cache_key_includes_kind_and_prefix():
    with tempfile.TemporaryDirectory() as d:
        CachedEmbedder(CountingEmbedder(), Path(d)).embed(['a'], 'passage')
        by_kind = CachedEmbedder(CountingEmbedder(), Path(d))
        by_kind.embed(['a'], 'query')
        assert by_kind.misses == 1
        by_prefix = CachedEmbedder(CountingEmbedder(passage_prefix='passage: '), Path(d))
        by_prefix.embed(['a'], 'passage')
        assert by_prefix.misses == 1


def test_cache_dir_inside_repo_refused():
    with pytest.raises(ValueError, match='inside_repo'):
        CachedEmbedder(CountingEmbedder(), ROOT / 'tmp_embed_cache_should_not_exist')
    assert not (ROOT / 'tmp_embed_cache_should_not_exist').exists()


def test_models_registry():
    assert MODELS['e5-base']['model_id'] == 'intfloat/multilingual-e5-base'
    assert MODELS['e5-base']['query_prefix'] == 'query: '
    assert MODELS['bge-m3']['max_tokens'] == 8192
    assert MODELS['voyage-4']['kind'] == 'cloud'


class TruncatingEmbedder(FakeEmbedder):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def embed(self, texts, kind):
        self.calls += 1
        out = super().embed(texts, kind)
        self.last_truncated = [t.startswith('long') for t in texts]
        self.truncated += sum(self.last_truncated)
        return out


def test_cached_truncated_count_survives_warm_cache():
    texts = ['long one', 'short', 'long two', 'long one']
    with tempfile.TemporaryDirectory() as d:
        cold = CachedEmbedder(TruncatingEmbedder(), Path(d))
        cold.embed(texts, 'passage')
        warm_inner = TruncatingEmbedder()
        warm = CachedEmbedder(warm_inner, Path(d))
        warm.embed(texts, 'passage')
        assert cold.truncated == warm.truncated == cold.truncated_texts == 2
        assert cold.truncated_requests == warm.truncated_requests == 3
        assert warm_inner.calls == 0 and warm.misses == 0


def test_cached_truncated_counts_unique_texts_across_calls():
    with tempfile.TemporaryDirectory() as d:
        emb = CachedEmbedder(TruncatingEmbedder(), Path(d))
        emb.embed(['long plan', 'short'], 'passage')
        emb.embed(['long plan'], 'passage')
        assert emb.truncated == 1 and emb.truncated_requests == 2


def test_truncated_embedder_slices_and_renormalizes():
    base = FakeEmbedder(dim=16)
    t = TruncatedEmbedder(base, 'fake-4', 4)
    full = base.embed(['a', 'b'], 'passage')
    out = t.embed(['a', 'b'], 'passage')
    assert out.shape == (2, 4)
    assert np.allclose(np.linalg.norm(out, axis=1), 1.0)
    assert np.allclose(out, full[:, :4] / np.linalg.norm(full[:, :4], axis=1, keepdims=True))
    assert t.key == 'fake-4' and t.model_id == base.model_id and t.dim == 4
    assert t.revision == base.revision and t.max_tokens == base.max_tokens and t.truncated == base.truncated
    assert t.last_truncated == base.last_truncated


def test_nano_specs():
    assert MODELS['nano-2048']['trust_remote_code'] is True
    assert MODELS['nano-2048']['dtype'] == 'float32'
    assert MODELS['nano-2048']['revision'] == '587d8d6dcaec029a9779c2098d6af020e4a07c01'
    assert MODELS['nano-512'] == {'kind': 'truncate', 'base': 'nano-2048', 'dim': 512}


def _stub_local(monkeypatch, dtype=None):
    """A LocalEmbedder for e5-base over stubbed torch / sentence_transformers: nothing is loaded."""
    import sys
    import types
    from memory_bench.embeddings import LocalEmbedder

    class Model:
        def __init__(self, *args, **kwargs):
            self.tokenizer = None

        def get_sentence_embedding_dimension(self):
            return 16
    torch = types.SimpleNamespace(set_num_threads=lambda n: None, float32='float32')
    monkeypatch.setitem(sys.modules, 'torch', torch)
    monkeypatch.setitem(sys.modules, 'sentence_transformers', types.SimpleNamespace(SentenceTransformer=Model))
    spec = MODELS['e5-base']
    return LocalEmbedder('e5-base', spec['model_id'], spec['revision'], spec['query_prefix'], spec['passage_prefix'],
                         spec['max_tokens'], dtype=dtype)


# sha256 of 'intfloat/multilingual-e5-base|<revision>|passage|passage: |alpha', taken from the code before dtype
# entered the key: e5 and bge-m3 caches built earlier stay valid.
E5_ALPHA_PASSAGE = '07f21e775d8849713d784ebf96268aeac5f81c6e1ced8f1161458d3120c339ed'


def test_cache_path_includes_dtype_and_keeps_e5_unchanged(monkeypatch, outside_dir):
    plain = CachedEmbedder(_stub_local(monkeypatch), outside_dir)
    typed = CachedEmbedder(_stub_local(monkeypatch, dtype='float32'), outside_dir)
    assert plain._path('passage', 'alpha').name == E5_ALPHA_PASSAGE + '.npz'
    assert typed._path('passage', 'alpha') != plain._path('passage', 'alpha')


class BatchedEmbedder(FakeEmbedder):
    BATCH = 3

    def __init__(self, fail_on_call=None):
        super().__init__()
        self.calls = []
        self.fail_on_call = fail_on_call

    def embed(self, texts, kind):
        self.calls.append(len(texts))
        if len(self.calls) == self.fail_on_call:
            raise ValueError('cloud_http_500')
        return super().embed(texts, kind)


def test_cache_writes_each_chunk_before_the_next(outside_dir):
    texts = [f't{i}' for i in range(8)]
    inner = BatchedEmbedder(fail_on_call=3)
    with pytest.raises(ValueError, match='cloud_http_500'):
        CachedEmbedder(inner, outside_dir).embed(texts, 'passage')
    assert inner.calls == [3, 3, 2] and len(list(outside_dir.glob('*.npz'))) == 6
    again = BatchedEmbedder()
    out = CachedEmbedder(again, outside_dir).embed(texts, 'passage')
    assert again.calls == [2] and np.array_equal(out, FakeEmbedder().embed(texts, 'passage'))
