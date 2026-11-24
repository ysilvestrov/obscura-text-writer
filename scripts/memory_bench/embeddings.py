"""Embedders for the vector bench (#25): a fake one for tests, a local sentence-transformers one, a disk cache.

Texts never leave this module except into the embedder itself; the cache stores vectors only, keyed by a hash.
numpy is required here; memory_bench.strategies and memory_bench.ranking stay importable without it."""
import hashlib
import os
from pathlib import Path
from typing import Literal, Protocol, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

# Revisions of the local models are placeholders: Task 8 pins the Hugging Face commit hash on the first download.
MODELS: dict[str, dict] = {
    'e5-base': {'kind': 'local', 'model_id': 'intfloat/multilingual-e5-base', 'revision': 'main',
                'query_prefix': 'query: ', 'passage_prefix': 'passage: ', 'max_tokens': 512},
    'bge-m3': {'kind': 'local', 'model_id': 'BAAI/bge-m3', 'revision': 'main',
               'query_prefix': '', 'passage_prefix': '', 'max_tokens': 8192},  # dense only
    # Azure deployment name; AzureEmbedder is added in Task 6.
    'azure-3-large': {'kind': 'cloud', 'model_id': 'text-embedding-3-large', 'revision': 'azure'},
}


class Embedder(Protocol):
    key: str
    model_id: str
    revision: str
    dim: int
    max_tokens: int
    truncated: int

    def embed(self, texts: Sequence[str], kind: Literal['query', 'passage']) -> np.ndarray: ...


def _normalized(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return (matrix / np.where(norms == 0, 1, norms)).astype(np.float32)


class FakeEmbedder:
    """Deterministic vectors from the sha256 of the text; no network, no model."""
    revision = 'fake'
    max_tokens = 1 << 30
    truncated = 0
    query_prefix = ''
    passage_prefix = ''

    def __init__(self, dim: int = 16):
        self.key = 'fake'
        self.model_id = 'fake'
        self.dim = dim

    def embed(self, texts, kind):
        rows = []
        for text in texts:
            raw = b''
            counter = 0
            while len(raw) < self.dim:
                raw += hashlib.sha256(f'{counter}|{text}'.encode('utf-8')).digest()
                counter += 1
            rows.append(np.frombuffer(raw[:self.dim], dtype=np.uint8).astype(np.float32) - 127.5)
        return _normalized(np.array(rows).reshape(len(rows), self.dim))


class LocalEmbedder:
    """sentence-transformers on CPU; the import lives in the constructor so the module loads without it."""

    def __init__(self, key, model_id, revision, query_prefix, passage_prefix, max_tokens, threads=1):
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(threads)
        self.key, self.model_id, self.revision = key, model_id, revision
        self.query_prefix, self.passage_prefix = query_prefix, passage_prefix
        self.max_tokens = max_tokens
        self.truncated = 0
        self._model = SentenceTransformer(model_id, revision=revision, device='cpu')
        self._model.max_seq_length = max_tokens
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts, kind):
        prefix = self.query_prefix if kind == 'query' else self.passage_prefix
        prepared = [prefix + t for t in texts]
        tokenizer = self._model.tokenizer
        self.truncated += sum(len(tokenizer(t, add_special_tokens=True)['input_ids']) > self.max_tokens for t in prepared)
        out = self._model.encode(prepared, batch_size=8, normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False)
        return _normalized(out)


def _inside_repo(path) -> bool:
    return Path(path).resolve().is_relative_to(ROOT.resolve())


class CachedEmbedder:
    """Per-text disk cache of vectors under cache_dir (outside the repository). hits / misses count texts."""

    def __init__(self, inner, cache_dir):
        if _inside_repo(cache_dir):
            raise ValueError('inside_repo')
        self.inner = inner
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def __getattr__(self, name):
        if name in ('key', 'model_id', 'revision', 'dim', 'max_tokens', 'truncated'):
            return getattr(self.inner, name)
        raise AttributeError(name)

    def _path(self, kind, text) -> Path:
        prefix = getattr(self.inner, 'query_prefix' if kind == 'query' else 'passage_prefix', '')
        raw = '|'.join((self.inner.model_id, self.inner.revision, kind, prefix, text))
        return self.cache_dir / (hashlib.sha256(raw.encode('utf-8')).hexdigest() + '.npy')

    def embed(self, texts, kind):
        paths = [self._path(kind, t) for t in texts]
        found: dict[Path, np.ndarray] = {}
        for p in paths:
            if p not in found and p.exists():
                found[p] = np.load(p)
        missing = list(dict.fromkeys((p, t) for p, t in zip(paths, texts) if p not in found))
        self.hits += sum(p in found for p in paths)
        self.misses += sum(p not in found for p in paths)
        if missing:
            vectors = self.inner.embed([t for _, t in missing], kind)
            for (p, _), vec in zip(missing, vectors):
                tmp = p.with_suffix(f'.{os.getpid()}.tmp')
                with open(tmp, 'wb') as f:
                    np.save(f, vec)
                os.replace(tmp, p)
                found[p] = vec
        if not paths:
            return np.zeros((0, self.inner.dim), dtype=np.float32)
        return np.stack([found[p] for p in paths]).astype(np.float32)
