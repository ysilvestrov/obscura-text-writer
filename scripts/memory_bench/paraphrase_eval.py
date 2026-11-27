"""Rank of the target record and in-context hits on paraphrased queries (Voyage retrieval bench, #25).

A paraphrase of a record is the query; the record it was generated from is the target. Per level (same / syn / desc),
per column (bm25, vec[model], hybrid[model]) and per form (standalone, in_plan) the module reports where the target
lands in the ranker's order and whether a later scene's structural + retrieval selection keeps it in memory.

Output holds counts, shares and ranks only: no query texts, no record texts. Importable without numpy."""
import math
import statistics
from dataclasses import replace
from typing import Callable, Mapping

from .model import Record, SceneInput
from .paraphrase import (FRAME_PARAMS, LEVELS, Query, _eligible, _sha, content_words, in_plan_scene, sampling_frame,
                         story_names)
from .ranking import Ranker
from .strategies import Params, full, record_layers

STEPS = (0.75, 0.5, 0.35)
CORES = ('upper', 'lower')
UNRELIABLE_SHARE = 0.10
CAP_K = 10  # primary sign test: ranks capped at CAP_K + 1, "not returned" counts as CAP_K + 1
_UNBOUNDED = Params(10 ** 12, 'realistic', 'upper')


def rank_of(target: str, ordered: list[Record]) -> int | None:
    """1-based place of the target in the ranker's order; None when the ranker did not return it."""
    for place, record in enumerate(ordered, 1):
        if record.claim_id == target:
            return place
    return None


def sign_test(a: list[int | None], b: list[int | None]) -> dict:
    """Paired two-sided exact sign test (same arithmetic as adhoc_2026_11_25/offline_checks.sign_test). Smaller rank
    wins; None is worse than any number and two None are a tie."""
    worst = float('inf')
    pairs = [(worst if x is None else x, worst if y is None else y) for x, y in zip(a, b)]
    a_better = sum(x < y for x, y in pairs)
    b_better = sum(x > y for x, y in pairs)
    n = a_better + b_better
    if n == 0:
        return {'a_better': a_better, 'b_better': b_better, 'ties': len(pairs), 'p': 1.0}
    k = min(a_better, b_better)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return {'a_better': a_better, 'b_better': b_better, 'ties': len(pairs) - n, 'p': round(p, 4)}


def capped(ranks: list[int | None], k: int = CAP_K) -> list[int]:
    """min(rank, k + 1), None as k + 1: past the top k a place carries no difference (rank 80 ties "not returned")."""
    return [k + 1 if r is None else min(r, k + 1) for r in ranks]


def strategy_name(column: str) -> str:
    """Strategy of a column: bm25 -> structural_fts, vec[m] -> structural_vec[m], hybrid[m] -> structural_hybrid[m];
    the contextual columns alike: ctx_bm25 -> structural_ctx_fts, ctx_vec[m] -> structural_ctx_vec[m]."""
    special = {'bm25': 'structural_fts', 'ctx_bm25': 'structural_ctx_fts'}
    return special.get(column) or f'structural_{column}'


def frame_by_id(scenes: list[SceneInput]) -> dict[str, Record]:
    return {r.claim_id: r for r in sampling_frame(scenes, FRAME_PARAMS)}


def stale_queries(queries: list[Query], scenes: list[SceneInput]) -> bool:
    """True when any query's record is gone from the sampling frame of the current extraction or its text changed
    (sha256 of the record text differs from the one stored when the query was generated)."""
    frame = frame_by_id(scenes)
    return any(q.claim_id not in frame or _sha(frame[q.claim_id].text) != q.record_sha256 for q in queries)


def _in_plan_pool(scene: SceneInput) -> list[Record]:
    layers = record_layers(scene, FRAME_PARAMS)
    return [r for r in scene.records if _eligible(r, layers)]


def _stats(ranks: list[int | None], n: int) -> dict:
    found = [r for r in ranks if r is not None]
    share = lambda k: (sum(1 for r in found if r <= k) / n) if n else 0.0
    return {'median_rank': float(statistics.median(found)) if found else None,
            'found': (len(found) / n) if n else 0.0, 'top5': share(5), 'top10': share(10)}


def evaluate_paraphrases(scenes: list[SceneInput], queries: list[Query], rankers: Mapping[str, Ranker],
                         strategies: Mapping[str, Callable], params_of: Callable[[int, str], Params],
                         steps: tuple[float, ...] = STEPS, plan_hits: dict | None = None) -> dict:
    """{level: {column: {n, rejected, rejected_by_category, few_content_words, unreliable, standalone, in_plan,
    sign_vs_bm25, sign_vs_bm25_raw, sign_in_context_vs_bm25}}}.

    params_of(budget_tokens, core_mode) builds the strategy Params. Rejected queries never enter n. Shares are of n:
    a query without a later scene (in_plan) or a target the ranker did not return counts as not found.

    The per-level counters rejected_by_category and few_content_words (targets with fewer than 2 content words, which
    can never pass 'same') repeat in every column cell, like rejected. The sign tests pair records (one query per record
    and level): sign_vs_bm25 on ranks capped at CAP_K + 1 (primary), sign_vs_bm25_raw on raw ranks with "not returned"
    worst (secondary), sign_in_context_vs_bm25[step][core] on per-record in-context hits of the in_plan form against
    structural_fts, the strategy of bm25. With plan_hits (plan_only_hits) every cell also gets
    sign_in_context_vs_plan[step][core]: the same records' in-context hits of the in_plan query against their plan-only
    hits (M6)."""
    frame = frame_by_id(scenes)
    names = story_names(scenes)
    pool_all = [frame[k] for k in sorted(frame)]
    by_scene = {s.scene_id: s for s in scenes}
    totals = {s.scene_id: full(s, _UNBOUNDED).tokens_realistic for s in scenes}
    pools: dict[str, list[Record]] = {}
    out: dict = {}
    for level in LEVELS:
        mine = [q for q in queries if q.level == level]
        ok = sorted((q for q in mine if q.status == 'ok'), key=lambda q: q.claim_id)
        rejected = sum(1 for q in mine if q.status == 'rejected')
        unreliable = bool(rejected + len(ok)) and rejected / (len(ok) + rejected) > UNRELIABLE_SHARE
        by_category: dict[str, int] = {}
        for item in mine:
            if item.status == 'rejected':
                category = frame[item.claim_id].category if item.claim_id in frame else 'unknown'
                by_category[category] = by_category.get(category, 0) + 1
        by_category = dict(sorted(by_category.items()))
        few = sum(1 for claim in {item.claim_id for item in mine}
                  if claim in frame and len(content_words(frame[claim].text, names)) < 2)
        targets = []  # per ok query: (query, frame record or None, scene or None)
        for q in ok:
            record = frame.get(q.claim_id)
            scene = in_plan_scene(record, scenes, FRAME_PARAMS) if record is not None else None
            if scene is not None:
                pools.setdefault(scene.scene_id, _in_plan_pool(scene))
            targets.append((q, record, scene))
        out[level] = {}
        ranks: dict[str, dict[str, list[int | None]]] = {}
        hit_lists: dict[str, dict[str, dict[str, list[int]]]] = {}
        for column, ranker in rankers.items():
            standalone = [rank_of(q.claim_id, ranker(pool_all, q.text)) for q, _, _ in targets]
            in_plan, hits = [], {str(step): {core: [] for core in CORES} for step in steps}
            no_scene = 0
            for q, record, scene in targets:
                if scene is None:
                    no_scene += 1
                    in_plan.append(None)
                    for step in steps:
                        for core in CORES:
                            hits[str(step)][core].append(0)
                    continue
                query = f'{scene.plan_text} {q.text}'
                in_plan.append(rank_of(q.claim_id, ranker(pools[scene.scene_id], query)))
                asked = replace(by_scene[scene.scene_id], plan_text=query)
                for step in steps:
                    budget = int(step * totals[scene.scene_id])
                    for core in CORES:
                        selected = strategies[strategy_name(column)](asked, params_of(budget, core))
                        hits[str(step)][core].append(int(q.claim_id in selected.record_ids))
            n = len(ok)
            ranks[column] = {'standalone': standalone, 'in_plan': in_plan}
            hit_lists[column] = hits
            out[level][column] = {
                'n': n, 'rejected': rejected, 'rejected_by_category': by_category, 'few_content_words': few,
                'unreliable': unreliable,
                'standalone': _stats(standalone, n),
                'in_plan': {**_stats(in_plan, n), 'no_scene': no_scene,
                            'in_context': {s: {core: (sum(hits[s][core]) / n if n else 0.0) for core in CORES}
                                           for s in hits}}}
            if plan_hits is not None:  # paired per record against the plan-only hit (M6); the test takes misses
                plan ={s: [[plan_hits[column][q.claim_id][s][core] for q, _, _ in targets] for core in CORES] for s in hits}
                out[level][column]['sign_in_context_vs_plan'] = {
                    s: {core: sign_test([1 - h for h in hits[s][core]], [1 - h for h in plan[s][i]])
                        for i, core in enumerate(CORES)} for s in hits}
        if 'bm25' in ranks:
            forms = ('standalone', 'in_plan')
            for column in rankers:
                if column != 'bm25':
                    mine_r, base_r = ranks[column], ranks['bm25']
                    cell = out[level][column]
                    cell['sign_vs_bm25'] = {f: sign_test(capped(mine_r[f]), capped(base_r[f])) for f in forms}
                    cell['sign_vs_bm25_raw'] = {f: sign_test(mine_r[f], base_r[f]) for f in forms}
                    # a hit is better: the test takes misses (1 - hit), where smaller wins
                    cell['sign_in_context_vs_bm25'] = {
                        s: {core: sign_test([1 - h for h in hit_lists[column][s][core]],
                                            [1 - h for h in hit_lists['bm25'][s][core]]) for core in CORES}
                        for s in hit_lists[column]}
    return out


def plan_only_hits(scenes: list[SceneInput], queries: list[Query], columns, strategies: Mapping[str, Callable],
                   params_of: Callable[[int, str], Params], steps: tuple[float, ...] = STEPS) -> dict:
    """{column: {claim_id: {step: {core: 0 | 1}}}}: whether the record lands in the selection of its in_plan scene when
    the query is that scene's plan alone (no paraphrase sentence). The selection does not depend on the level, so it is
    computed once per record with an ok query at any level. A record gone from the frame or without a later scene is a
    miss (0), like in_context."""
    frame = frame_by_id(scenes)
    totals = {s.scene_id: full(s, _UNBOUNDED).tokens_realistic for s in scenes}
    claims = sorted({q.claim_id for q in queries if q.status == 'ok'})
    placed = [(c, in_plan_scene(frame[c], scenes, FRAME_PARAMS) if c in frame else None) for c in claims]
    out = {}
    for column in columns:
        strategy = strategies[strategy_name(column)]
        out[column] = {}
        for claim, scene in placed:
            cell = {str(step): {core: 0 for core in CORES} for step in steps}
            if scene is not None:
                for step in steps:
                    for core in CORES:
                        selected = strategy(scene, params_of(int(step * totals[scene.scene_id]), core))
                        cell[str(step)][core] = int(claim in selected.record_ids)
            out[column][claim] = cell
    return out


def evaluate_baseline_plan(scenes: list[SceneInput], queries: list[Query], columns, strategies: Mapping[str, Callable],
                           params_of: Callable[[int, str], Params], steps: tuple[float, ...] = STEPS,
                           hits: dict | None = None) -> dict:
    """M6 baseline of the in_plan in-context hits: {'n': {level: n}, 'levels': {level: {column: {step: {core: share}}}}}.

    Per-record plan-only hits (plan_only_hits, computed once; pass `hits` to reuse them) are aggregated per level over
    that level's ok queries, so n and the population equal those of the level's in_context."""
    hits = hits if hits is not None else plan_only_hits(scenes, queries, columns, strategies, params_of, steps)
    n_of, levels = {}, {}
    for level in LEVELS:
        claims = [q.claim_id for q in queries if q.level == level and q.status == 'ok']
        n = n_of[level] = len(claims)
        levels[level] = {column: {str(step): {core: (sum(hits[column][c][str(step)][core] for c in claims) / n if n else 0.0)
                                              for core in CORES} for step in steps} for column in columns}
    return {'n': n_of, 'levels': levels}
