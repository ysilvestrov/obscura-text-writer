"""Ranking diagnostic without layers: where annotated records land in a bare ranker's order.
Output holds pair counts and ranks only: no texts, no claim IDs. Stays importable without numpy."""
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
