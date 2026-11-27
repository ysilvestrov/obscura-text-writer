"""Embedders for the vector bench (#25): a fake one for tests, a local sentence-transformers one, a disk cache.

Texts never leave this module except into the embedder itself; the cache stores vectors only, keyed by a hash.
numpy is required here; memory_bench.strategies and memory_bench.ranking stay importable without it."""
import hashlib
import math
import os
import sys
import time
from pathlib import Path
from typing import Literal, Protocol, Sequence

import numpy as np

from memory_bench.paraphrase import _inside_repo  # noqa: F401  (single copy; re-exported for the CLI)

ROOT = Path(__file__).resolve().parents[2]

MODELS: dict[str, dict] = {
    'e5-base': {'kind': 'local', 'model_id': 'intfloat/multilingual-e5-base', 'revision': 'd128750597153bb5987e10b1c3493a34e5a4502a',
                'query_prefix': 'query: ', 'passage_prefix': 'passage: ', 'max_tokens': 512},
    'bge-m3': {'kind': 'local', 'model_id': 'BAAI/bge-m3', 'revision': '5617a9f61b028005a4858fdac845db406aefb181',
               'query_prefix': '', 'passage_prefix': '', 'max_tokens': 8192},  # dense only
    # Voyage 4 nano (Matryoshka): the modeling code comes from the pinned revision (trust_remote_code); nano-512 is the
    # first 512 coordinates of nano-2048, re-normalized, over the same loaded model and the same cache.
    'nano-2048': {'kind': 'local', 'model_id': 'MongoDB/voyage-4-nano', 'revision': '587d8d6dcaec029a9779c2098d6af020e4a07c01',
                  'query_prefix': 'Represent the query for retrieving supporting documents: ',
                  'passage_prefix': 'Represent the document for retrieval: ', 'max_tokens': 8192, 'trust_remote_code': True,
                  'dtype': 'float32'},  # the checkpoint is bf16, which is very slow on CPU
    'nano-512': {'kind': 'truncate', 'base': 'nano-2048', 'dim': 512},
    # Azure deployment name comes from the cloud config, not from here; the client is AzureEmbedder.
    'azure-3-large': {'kind': 'cloud', 'model_id': 'text-embedding-3-large', 'revision': 'azure'},
}


class Embedder(Protocol):
    key: str
    model_id: str
    revision: str
    dim: int
    max_tokens: int
    truncated: int
    last_truncated: list[bool]  # per text of the latest embed call: was it longer than max_tokens

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
        self.last_truncated = [False] * len(texts)
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

    def __init__(self, key, model_id, revision, query_prefix, passage_prefix, max_tokens, threads=1,
                 trust_remote_code=False, dtype: str | None = None):
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(threads)
        self.key, self.model_id, self.revision = key, model_id, revision
        self.query_prefix, self.passage_prefix = query_prefix, passage_prefix
        self.max_tokens = max_tokens
        self.truncated = 0
        self._model = SentenceTransformer(model_id, revision=revision, device='cpu',
                                          trust_remote_code=trust_remote_code,
                                          model_kwargs={'dtype': getattr(torch, dtype)} if dtype else None)
        self._model.max_seq_length = max_tokens
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts, kind):
        prefix = self.query_prefix if kind == 'query' else self.passage_prefix
        prepared = [prefix + t for t in texts]
        tokenizer = self._model.tokenizer
        self.last_truncated = [len(tokenizer(t, add_special_tokens=True)['input_ids']) > self.max_tokens for t in prepared]
        self.truncated += sum(self.last_truncated)
        out = self._model.encode(prepared, batch_size=8, normalize_embeddings=True, convert_to_numpy=True,
                                 show_progress_bar=False)
        return _normalized(out)


class TruncatedEmbedder:
    """First `dim` coordinates of the base embedder's vectors, re-normalized (Matryoshka). Everything but key and dim
    (and the vectors) comes from the base; the base is usually the CachedEmbedder of the full model, so its cache and
    counters are shared and the model is loaded once."""
    _DELEGATED = frozenset({'model_id', 'revision', 'max_tokens', 'truncated', 'last_truncated', 'query_prefix',
                            'passage_prefix', 'truncated_requests', 'cache_dir', 'hits', 'misses'})

    def __init__(self, base, key: str, dim: int):
        self.base, self.key, self.dim = base, key, dim

    def __getattr__(self, name):
        if name in self._DELEGATED:
            return getattr(self.base, name)
        raise AttributeError(name)

    def embed(self, texts, kind):
        return _normalized(self.base.embed(texts, kind)[:, :self.dim])


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
        self._truncated_paths: set[Path] = set()  # unique cache entries seen truncated: warm and cold agree
        self.truncated_requests = 0  # per occurrence, cache hits included
        self.last_truncated: list[bool] = []

    @property
    def truncated_texts(self) -> int:
        return len(self._truncated_paths)

    @property
    def truncated(self) -> int:  # texts longer than max_tokens, each counted once
        return len(self._truncated_paths)

    def __getattr__(self, name):
        if name in ('key', 'model_id', 'revision', 'dim', 'max_tokens'):
            return getattr(self.inner, name)
        raise AttributeError(name)

    def _path(self, kind, text) -> Path:
        prefix = getattr(self.inner, 'query_prefix' if kind == 'query' else 'passage_prefix', '')
        raw = '|'.join((self.inner.model_id, self.inner.revision, kind, prefix, text))
        return self.cache_dir / (hashlib.sha256(raw.encode('utf-8')).hexdigest() + '.npz')

    def embed(self, texts, kind):
        paths = [self._path(kind, t) for t in texts]
        found: dict[Path, tuple[np.ndarray, bool]] = {}
        for p in paths:
            if p not in found and p.exists():
                with np.load(p) as data:
                    found[p] = (data['vec'], bool(data['truncated']))
        missing = list(dict.fromkeys((p, t) for p, t in zip(paths, texts) if p not in found))
        self.hits += sum(p in found for p in paths)
        self.misses += sum(p not in found for p in paths)
        if missing:
            vectors = self.inner.embed([t for _, t in missing], kind)
            flags = getattr(self.inner, 'last_truncated', None) or [False] * len(missing)
            for (p, _), vec, flag in zip(missing, vectors, flags):
                tmp = p.with_suffix(f'.{os.getpid()}.tmp')
                with open(tmp, 'wb') as f:
                    np.savez(f, vec=vec, truncated=np.array(flag))
                os.replace(tmp, p)
                found[p] = (vec, bool(flag))
        self.last_truncated = [found[p][1] for p in paths]
        self.truncated_requests += sum(self.last_truncated)
        self._truncated_paths.update(p for p in paths if found[p][1])
        if not paths:
            return np.zeros((0, self.inner.dim), dtype=np.float32)
        return np.stack([found[p][0] for p in paths]).astype(np.float32)


def cloud_allowed(story_id: str, prefixes: Sequence[str]) -> bool:
    """True only for a story whose id starts with one of the non-empty allowed prefixes."""
    return any(p and story_id.startswith(p) for p in prefixes)


class AzureEmbedder:
    """Azure OpenAI embeddings over httpx, in batches, with a hard budget check before any request.

    Texts go only into the request body; neither texts nor the api key appear in exceptions. No prefix is added for
    either kind. Truncation is not measured for the cloud model: last_truncated is all False and truncated stays 0."""
    BATCH = 64

    def __init__(self, key, endpoint, api_key, deployment, api_version, price_per_mtok: float, max_usd: float,
                 transport=None, model_id='text-embedding-3-large', revision='azure', dim=0):
        import httpx
        self.key, self.model_id, self.revision, self.dim = key, model_id, revision, dim
        self.max_tokens = 8191
        self.truncated = 0
        self.last_truncated: list[bool] = []
        self.query_prefix = self.passage_prefix = ''
        self.price_per_mtok, self.max_usd = price_per_mtok, max_usd
        self.tokens, self.usd = 0, 0.0
        self.latencies: list[float] = []
        self._url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings"
        self._api_version = api_version
        self._headers = {'api-key': api_key}
        self._client = httpx.Client(transport=transport, timeout=60.0)

    def close(self):
        self._client.close()

    def embed(self, texts, kind):
        texts = list(texts)
        self.last_truncated = [False] * len(texts)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        estimate = sum(math.ceil(len(t) / 2) for t in texts)
        est_usd = estimate * self.price_per_mtok / 1e6
        print(f'cloud_estimate tokens={estimate} usd={est_usd:.4f} spent_usd={self.usd:.4f} max_usd={self.max_usd}',
              file=sys.stderr)
        if self.usd + est_usd > self.max_usd:
            raise ValueError('cloud_budget')
        rows = []
        for start in range(0, len(texts), self.BATCH):
            batch = texts[start:start + self.BATCH]
            began = time.perf_counter()
            try:
                response = self._client.post(self._url, params={'api-version': self._api_version},
                                             headers=self._headers, json={'input': batch})
                response.raise_for_status()
                body = response.json()
            except Exception as error:  # message never echoes the body, texts or the key
                status = getattr(getattr(error, 'response', None), 'status_code', None)
                raise ValueError(f'cloud_http_{status}' if status else 'cloud_error') from None
            self.latencies.append(time.perf_counter() - began)
            try:
                used = int(body['usage']['prompt_tokens'])
                batch_rows = [item['embedding'] for item in sorted(body['data'], key=lambda item: item['index'])]
            except (KeyError, TypeError):  # malformed body: never echo it
                raise ValueError('cloud_bad_response') from None
            self.tokens += used
            self.usd += used * self.price_per_mtok / 1e6
            rows.extend(batch_rows)
        matrix = _normalized(np.array(rows, dtype=np.float32))
        self.dim = int(matrix.shape[1])
        return matrix
