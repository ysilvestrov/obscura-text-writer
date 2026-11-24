import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

np = pytest.importorskip('numpy')

from memory_bench.embeddings import ROOT, CachedEmbedder, FakeEmbedder, MODELS  # noqa: E402


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
    assert MODELS['azure-3-large']['kind'] == 'cloud'


def test_embeddings_module_optional():
    code = ("import sys, memory_bench.strategies, memory_bench.ranking;"
            "assert 'sentence_transformers' not in sys.modules; assert 'numpy' not in sys.modules")
    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, '-c', code], check=True, cwd=root,
                   env={**__import__('os').environ, 'PYTHONPATH': str(root / 'scripts') + ';' + str(root)})
