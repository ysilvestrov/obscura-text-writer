"""Ranking diagnostic without layers: where annotated records land in a bare ranker's order.
Output holds pair counts and ranks only: no texts, no claim IDs. Stays importable without numpy."""
from dataclasses import replace
from statistics import median
from typing import Callable, Mapping

from .model import Record, SceneInput

Ranker = Callable[[list[Record], str], list[Record]]
CUTOFFS = (5, 10, 20)


def ranking_pool(scene: SceneInput) -> list[Record]:
    return [r for r in scene.records if r.category != 'timeline']


def pair_ranks(rankers: Mapping[str, Ranker], annotation: Mapping[str, list[str]], pairs: dict,
               scenes_by_number: Mapping[int, SceneInput]) -> dict:
    """Per ranker and kind (pair / control): recall@5/10/20 counts, ranked-pair total, median best rank.
    A pair's rank is the best 1-based rank of its annotated records; a record the ranker did not return is a miss.
    Pairs not annotated, with a missing repeat scene or with no annotated record in the pool are not counted."""
    out = {name: {} for name in rankers}
    for kind, key in (('pair', 'pairs'), ('control', 'controls')):
        counted = []
        for entry in pairs.get(key, []):
            ids = set(annotation.get(entry['id']) or ())
            scene = scenes_by_number.get(entry['repeat'])
            if not ids or scene is None:
                continue
            pool = ranking_pool(scene)
            present = ids & {r.claim_id for r in pool}
            if present:
                counted.append((present, pool, scene.plan_text))
        for name, ranker in rankers.items():
            ranks = []
            for present, pool, query in counted:
                order = [r.claim_id for r in ranker(pool, query)]
                ranks.append(min((i for i, cid in enumerate(order, 1) if cid in present), default=float('inf')))
            finite = [r for r in ranks if r != float('inf')]
            out[name][kind] = {'recall_at': {str(k): sum(r <= k for r in ranks) for k in CUTOFFS},
                               'total': len(ranks), 'median_rank': float(median(finite)) if finite else None}
    return out


def _vector_order(candidates: list[Record], query_text: str, embedder) -> list[Record]:
    import numpy as np  # lazy: this module stays importable without numpy
    if query_text.strip() == '' or not candidates:
        return []
    query = embedder.embed([query_text], 'query')[0]
    matrix = embedder.embed([r.text for r in candidates], 'passage')
    scores = np.round((matrix @ query).astype(np.float64), 6)
    order = sorted(range(len(candidates)), key=lambda i: (-float(scores[i]), candidates[i].claim_id))
    return [candidates[i] for i in order]


def vec_rank(candidates: list[Record], query_text: str, embedder) -> list[Record]:
    """Cosine of L2-normalized vectors rounded to 1e-6; ties by claim_id. Empty query ranks nothing."""
    return _vector_order(candidates, query_text, embedder)


def rrf_rank(candidates: list[Record], query_text: str, embedder, k: int = 60) -> list[Record]:
    """Reciprocal rank fusion of BM25 and vector ranks (1-based, no threshold); a record absent from BM25 has only the
    vector part. Ties by claim_id."""
    from .strategies import fts_rank
    vec = _vector_order(candidates, query_text, embedder)
    if not vec:
        return []
    score = {r.claim_id: 1 / (k + i) for i, r in enumerate(vec, 1)}
    for i, r in enumerate(fts_rank(candidates, query_text), 1):
        score[r.claim_id] += 1 / (k + i)
    return sorted(vec, key=lambda r: (-score[r.claim_id], r.claim_id))


def contextual(ranker: Ranker, search_text: Mapping[str, str]) -> Ranker:
    """A ranker over proxy copies whose text is search_text[claim_id] (own text when absent); returns the original pool
    objects in the proxies' order, so the budget, record_ids and rendered memory never see the search text."""
    def ranked(candidates: list[Record], query_text: str) -> list[Record]:
        proxies = [replace(r, text=search_text.get(r.claim_id, r.text)) for r in candidates]
        original = {id(p): r for p, r in zip(proxies, candidates)}
        return [original[id(p)] for p in ranker(proxies, query_text)]
    return ranked


def contextual_versions(ranker: Ranker, versions: Mapping[tuple[str, str], str]) -> Ranker:
    """contextual() for a story where one claim has several texts over time (an updated record has another text and
    another source scene, so another context): versions maps (claim_id, record text) to the search text, and each call
    picks the version its pool holds (a pool holds one version per claim)."""
    def ranked(candidates: list[Record], query_text: str) -> list[Record]:
        search = {r.claim_id: versions[(r.claim_id, r.text)] for r in candidates if (r.claim_id, r.text) in versions}
        return contextual(ranker, search)(candidates, query_text)
    return ranked
