"""Ad-hoc research script, 25.11.2026 (not part of the product or the test suite).
Research venv only; then main_pipe.py (pipeline variants) and blocking.py (fts+fill, per-scene test, repeat wording).
Offline checks 1-4 for the vector bench (#25). Prints aggregates only: no texts, no claim IDs, no names.

1 oracle ranker in the pipeline (upper bound of any ranker);
2 lexical overlap of pairs + query masking;
3 sentence-level max-sim queries;
4 rank vs pool size on the main work."""
import json
import os
import math
import re
import sys
from pathlib import Path
from statistics import median

WT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(WT / 'src'))
sys.path.insert(0, str(WT / 'scripts'))

import numpy as np  # noqa: E402
from memory_bench.embeddings import MODELS, CachedEmbedder, LocalEmbedder  # noqa: E402
from memory_bench.extract import extract_story, name_stems  # noqa: E402
from memory_bench.metrics import pair_hits, pair_summary, scene_metrics, aggregate  # noqa: E402
from memory_bench.model import set_tokenizer  # noqa: E402
from memory_bench.ranking import ranking_pool, vec_rank, rrf_rank  # noqa: E402
from memory_bench.strategies import Params, full, fts_rank, _structural_retrieval, _WORD, _norm  # noqa: E402
from storygen.storage.repository import Repository  # noqa: E402

DATA = Path(os.environ.get('RAG_BENCH_DATA', r'C:\tmp\rag-bench\data'))  # a COPY of the data directory
CACHE = Path(os.environ.get('RAG_BENCH_CACHE', r'C:\tmp\rag-bench\cache'))  # outside the repository
STORY_A = '858693d46dd74894aeac548a6ec030e5'
PAIRS = json.loads((WT / 'docs/superpowers/notes/2026-11-24-rag-test-pairs.json').read_text(encoding='utf-8'))
ANNOT = json.loads((WT / 'docs/research/data/2026-11-24-rag-pairs-annotation.json').read_text(encoding='utf-8'))['stories'][STORY_A]
STEPS = (1.0, 0.75, 0.5, 0.35, 0.25)
PREFIX = 5

set_tokenizer('qwen3')


def embedder(key):
    s = MODELS[key]
    inner = LocalEmbedder(key, s['model_id'], s['revision'], s['query_prefix'], s['passage_prefix'], s['max_tokens'], threads=1)
    return CachedEmbedder(inner, CACHE / key)


def stems(text):
    return {w[:PREFIX] for w in _WORD.findall(_norm(text)) if len(w) >= 3}


def sentences(text):
    parts = [p.strip() for p in re.split(r'(?<=[.!?…])\s+|\n+', text) if len(p.strip()) >= 12]
    return parts or [text]


def maxsim_rank(pool, query, emb):
    if not pool or not query.strip():
        return []
    q = emb.embed(sentences(query), 'query')
    m = emb.embed([r.text for r in pool], 'passage')
    scores = np.round((m @ q.T).max(axis=1).astype(np.float64), 6)
    order = sorted(range(len(pool)), key=lambda i: (-float(scores[i]), pool[i].claim_id))
    return [pool[i] for i in order]


def bm25_sent_rank(pool, query):
    """Best per-sentence BM25 rank (reciprocal-rank max over sentences)."""
    best = {}
    for s in sentences(query):
        for i, r in enumerate(fts_rank(pool, s), 1):
            best[r.claim_id] = max(best.get(r.claim_id, 0), 1 / i)
    return sorted([r for r in pool if r.claim_id in best], key=lambda r: (-best[r.claim_id], r.claim_id))


def masked(query, drop):
    return ' '.join(w for w in re.split(r'\s+', query) if not any(t[:PREFIX] in drop for t in _WORD.findall(_norm(w)) if len(t) >= 3))


def best_rank(order, present):
    return min((i for i, r in enumerate(order, 1) if r.claim_id in present), default=math.inf)


def summarize(ranks):
    fin = [r for r in ranks if r != math.inf]
    return {'n': len(ranks), 'top5': sum(r <= 5 for r in ranks), 'top10': sum(r <= 10 for r in ranks),
            'top20': sum(r <= 20 for r in ranks), 'median': float(median(fin)) if fin else None}


def sign_test(a, b):
    """Two-sided exact sign test on paired ranks: (a better, b better, ties, p)."""
    wa = sum(x < y for x, y in zip(a, b)); wb = sum(x > y for x, y in zip(a, b)); n = wa + wb
    if n == 0:
        return wa, wb, len(a), 1.0
    k = min(wa, wb)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
    return wa, wb, len(a) - n, round(p, 4)


def main():
    repo = Repository(DATA)
    stories = repo.list_stories()
    main_story = max(stories, key=lambda s: (len(repo.list_scenes(s.id)), s.id))
    out = {}
    embs = {k: embedder(k) for k in ('e5-base', 'bge-m3')}

    # ---------- Text A ----------
    scenes, _ = extract_story(repo, STORY_A)
    by_num = {s.number: s for s in scenes}
    all_names = set()
    for s in scenes:
        for n in s.names.values():
            all_names |= {x[:PREFIX] for x in name_stems(n)}
    entries = [(k, e) for k, key in (('pair', 'pairs'), ('control', 'controls')) for e in PAIRS[key]]

    # check 1: oracle in the pipeline, budget steps
    totals = {s.scene_id: full(s, Params(10 ** 12, 'realistic', 'upper')).tokens_realistic for s in scenes}
    gold = {}
    for kind, e in entries:
        gold.setdefault(e['repeat'], set()).update(ANNOT.get(e['id']) or ())
    scene_by_query = {}
    def oracle(pool, query):
        num = scene_by_query[query]
        g = gold.get(num, set())
        base = fts_rank(pool, query)
        rest = [r for r in pool if r not in base]
        return [r for r in pool if r.claim_id in g] + [r for r in base + rest if r.claim_id not in g]
    for s in scenes:
        scene_by_query[s.plan_text] = s.number
    rankers_pipe = {'structural_fts': fts_rank, 'oracle': oracle,
                    'vec[bge-m3]': lambda p, q: vec_rank(p, q, embs['bge-m3']),
                    'maxsim[bge-m3]': lambda p, q: maxsim_rank(p, q, embs['bge-m3'])}
    c1 = {}
    for step in STEPS:
        c1[str(step)] = {}
        for name, rk in rankers_pipe.items():
            strat = _structural_retrieval(name, 'fts', rk)
            for mode in ('upper', 'lower'):
                sels = {s.number: strat(s, Params(int(step * totals[s.scene_id]), 'realistic', mode)) for s in scenes}
                ps = pair_summary(pair_hits(ANNOT, PAIRS, by_num, sels))
                ordered = [sels[s.number] for s in scenes]
                agg = aggregate([scene_metrics(s, x) for s, x in zip(scenes, ordered)], ordered)
                c1[str(step)][f'{name}[{mode}]'] = {'pairs': f"{ps['pair']['hit']}/{ps['pair']['total']}",
                                                    'pairs_by_retrieval': ps['pair']['by_retrieval'],
                                                    'controls': f"{ps['control']['hit']}/{ps['control']['total']}",
                                                    'targets_hit': round(agg['target_recall'] * agg['targets_total']),
                                                    'targets_total': agg['targets_total']}
    out['check1_oracle_textA'] = c1

    # checks 2 and 3: ranking diagnostic with variants of query and ranker
    counted = []
    for kind, e in entries:
        ids = set(ANNOT.get(e['id']) or ())
        s = by_num.get(e['repeat'])
        if not ids or s is None:
            continue
        pool = ranking_pool(s)
        present = ids & {r.claim_id for r in pool}
        if not present:
            continue
        target_stems = set().union(*(stems(r.text) for r in pool if r.claim_id in present))
        q = s.plan_text
        shared = stems(q) & target_stems
        counted.append({'id': e['id'], 'kind': kind, 'pool': pool, 'present': present, 'query': q,
                        'shared': len(shared), 'shared_names': len(shared & all_names), 'pool_size': len(pool),
                        'q_mask_names': masked(q, all_names), 'q_mask_shared': masked(q, shared),
                        'sentences': len(sentences(q))})
    out['check2_overlap'] = [{'id': c['id'], 'kind': c['kind'], 'shared_stems': c['shared'],
                              'shared_name_stems': c['shared_names'], 'pool': c['pool_size'],
                              'plan_sentences': c['sentences']} for c in counted]
    rankers = {'bm25': lambda p, q: fts_rank(p, q), 'bm25_sent': bm25_sent_rank}
    for k, e in embs.items():
        rankers[f'vec[{k}]'] = lambda p, q, e=e: vec_rank(p, q, e)
        rankers[f'maxsim[{k}]'] = lambda p, q, e=e: maxsim_rank(p, q, e)
        rankers[f'hybrid[{k}]'] = lambda p, q, e=e: rrf_rank(p, q, e)
    diag = {}
    per_pair = {}
    for qkey in ('query', 'q_mask_names', 'q_mask_shared'):
        diag[qkey] = {}
        for name, rk in rankers.items():
            for kind in ('pair', 'control'):
                rs = [best_rank(rk(c['pool'], c[qkey]), c['present']) for c in counted if c['kind'] == kind]
                diag[qkey][f'{name}/{kind}'] = summarize(rs)
            per_pair[f'{qkey}/{name}'] = {c['id']: (None if (r := best_rank(rk(c['pool'], c[qkey]), c['present'])) == math.inf else r)
                                          for c in counted}
    out['check2_3_ranking_textA'] = diag
    out['check2_3_per_pair_ranks'] = per_pair

    # ---------- Main work: check 1 (oracle on changing targets) and check 4 (rank vs pool size) ----------
    mscenes, _ = extract_story(repo, main_story.id)
    tot_m = {s.scene_id: full(s, Params(10 ** 12, 'realistic', 'upper')).tokens_realistic for s in mscenes}
    tq = {s.plan_text: s for s in mscenes}
    def oracle_m(pool, query):
        g = tq[query].targets
        base = fts_rank(pool, query)
        rest = [r for r in pool if r not in base]
        return [r for r in pool if r.claim_id in g] + [r for r in base + rest if r.claim_id not in g]
    c1m = {}
    for step in STEPS:
        c1m[str(step)] = {}
        for name, rk in (('structural_fts', fts_rank), ('oracle', oracle_m),
                         ('vec[bge-m3]', lambda p, q: vec_rank(p, q, embs['bge-m3']))):
            strat = _structural_retrieval(name, 'fts', rk)
            for mode in ('upper', 'lower'):
                sels = [strat(s, Params(int(step * tot_m[s.scene_id]), 'realistic', mode)) for s in mscenes]
                agg = aggregate([scene_metrics(s, x) for s, x in zip(mscenes, sels)], sels)
                c1m[str(step)][f'{name}[{mode}]'] = f"{round(agg['target_recall'] * agg['targets_total'])}/{agg['targets_total']}"
    out['check1_oracle_main'] = c1m

    rk4 = {'bm25': fts_rank, 'bm25_sent': bm25_sent_rank}
    for k, e in embs.items():
        rk4[f'vec[{k}]'] = lambda p, q, e=e: vec_rank(p, q, e)
        rk4[f'maxsim[{k}]'] = lambda p, q, e=e: maxsim_rank(p, q, e)
    rows = []  # (pool size, {ranker: rank}) per target present in the pool
    for s in mscenes:
        pool = ranking_pool(s)
        tg = s.targets & {r.claim_id for r in pool}
        if not tg:
            continue
        orders = {n: [r.claim_id for r in rk(pool, s.plan_text)] for n, rk in rk4.items()}
        for t in tg:
            rows.append((len(pool), {n: (o.index(t) + 1 if t in o else math.inf) for n, o in orders.items()}))
    rows.sort(key=lambda x: x[0])
    third = max(1, len(rows) // 3)
    bins = [rows[:third], rows[third:2 * third], rows[2 * third:]]
    c4 = {'targets_in_pool': len(rows), 'bins': []}
    for b in bins:
        if not b:
            continue
        entry = {'pool_min': b[0][0], 'pool_max': b[-1][0], 'n': len(b)}
        for n in rk4:
            rs = [r[n] for _, r in b]
            entry[n] = summarize(rs)
            entry[n]['median_pct'] = round(median([min(r, p) / p for (p, x), r in zip(b, rs)]), 3)
        c4['bins'].append(entry)
    c4['sign_bm25_vs'] = {n: sign_test([r['bm25'] for _, r in rows], [r[n] for _, r in rows]) for n in rk4 if n != 'bm25'}
    c4['sign_bm25_vs_by_bin'] = [{n: sign_test([r['bm25'] for _, r in b], [r[n] for _, r in b]) for n in rk4 if n != 'bm25'}
                                 for b in bins if b]
    out['check4_main_rank_vs_pool'] = c4
    print(json.dumps(out, ensure_ascii=True, indent=1, default=str))


if __name__ == '__main__':
    main()
