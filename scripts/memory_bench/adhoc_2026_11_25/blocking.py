import json, sys, math
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from offline_checks import *  # noqa
from offline_checks import _structural_retrieval  # noqa
from memory_bench.strategies import record_layers
from statistics import mean
repo = Repository(DATA)
E = {k: embedder(k) for k in ('e5-base', 'bge-m3')}
def fill(p, q):
    base = fts_rank(p, q); ids = {r.claim_id for r in base}
    return base + sorted([r for r in p if r.claim_id not in ids], key=lambda r: r.claim_id)
out = {}
# --- pipelines with fts+fill
def pipe(sc, steps, gold_of):
    tot = {s.scene_id: full(s, Params(10**12, 'realistic', 'upper')).tokens_realistic for s in sc}
    tq = {s.plan_text: s for s in sc}
    def oracle(p, q):
        g = gold_of(tq[q]); base = fill(p, q)
        return [r for r in p if r.claim_id in g] + [r for r in base if r.claim_id not in g]
    rk = {'fts': fts_rank, 'fts+fill': fill, 'oracle': oracle,
          'vec[e5]': lambda p, q: vec_rank(p, q, E['e5-base']), 'vec[bge]': lambda p, q: vec_rank(p, q, E['bge-m3'])}
    res = {}
    for step in steps:
        for mode in ('upper', 'lower'):
            row = {}
            for n, r in rk.items():
                st = _structural_retrieval(n, 'fts', r)
                sels = [st(s, Params(int(step * tot[s.scene_id]), 'realistic', mode)) for s in sc]
                a = aggregate([scene_metrics(s, x) for s, x in zip(sc, sels)], sels)
                row[n] = [round(a['target_recall'] * a['targets_total']), a['chars']['mean']]
            res[f'{step}/{mode}'] = row
    return res
st_main = max(repo.list_stories(), key=lambda s: (len(repo.list_scenes(s.id)), s.id))
msc, _ = extract_story(repo, st_main.id)
out['main_pipe'] = pipe(msc, (1.0, 0.9, 0.75, 0.6, 0.5, 0.42, 0.35), lambda s: s.targets)
asc, _ = extract_story(repo, STORY_A)
out['A_pipe_targets_oracle'] = pipe(asc, (1.0, 0.75, 0.5), lambda s: s.targets)
# --- check 4 details
rk4 = {'bm25': fts_rank, 'fts+fill': fill, 'vec[e5]': lambda p, q: vec_rank(p, q, E['e5-base']),
       'vec[bge]': lambda p, q: vec_rank(p, q, E['bge-m3'])}
rows, per_scene = [], []
for s in msc:
    pool = ranking_pool(s); tg = s.targets & {r.claim_id for r in pool}
    if not tg: continue
    lay = record_layers(s, Params(0, 'realistic', 'upper'))
    orders = {n: [r.claim_id for r in f(pool, s.plan_text)] for n, f in rk4.items()}
    sr = {}
    for t in tg:
        rr = {n: (o.index(t) + 1 if t in o else math.inf) for n, o in orders.items()}
        rows.append({'pool': len(pool), 'scene': s.number, 'in_layer': t in lay, 'bm25_miss': rr['bm25'] == math.inf, **rr})
        for n, v in rr.items(): sr.setdefault(n, []).append(min(v, len(pool)) / len(pool))
    per_scene.append({n: mean(v) for n, v in sr.items()})
c = {'targets': len(rows), 'scenes': len(per_scene), 'bm25_not_returned': sum(r['bm25_miss'] for r in rows),
     'targets_in_upper_layers': sum(r['in_layer'] for r in rows)}
for n in ('vec[e5]', 'vec[bge]'):
    c[f'target_sign_fill_vs_{n}'] = sign_test([r['fts+fill'] for r in rows], [r[n] for r in rows])
    c[f'scene_sign_fill_vs_{n}'] = sign_test([x['fts+fill'] for x in per_scene], [x[n] for x in per_scene])
    nl = [r for r in rows if not r['in_layer']]
    c[f'not_in_layer_sign_fill_vs_{n}'] = sign_test([r['fts+fill'] for r in nl], [r[n] for r in nl])
    hit = [r for r in rows if not r['bm25_miss']]
    c[f'bm25_returned_sign_bm25_vs_{n}'] = sign_test([r['bm25'] for r in hit], [r[n] for r in hit])
c['not_in_layer_n'] = sum(not r['in_layer'] for r in rows)
for n in rk4: c[f'mean_scene_pct_{n}'] = round(mean(x[n] for x in per_scene), 3)
out['check4_detail'] = c
# --- check 2': repeat wording alone as query, first wording as positive control
byn = {s.number: s for s in asc}
q2 = {}
rk2 = {'bm25': fill, 'vec[e5]': lambda p, q: vec_rank(p, q, E['e5-base']), 'vec[bge]': lambda p, q: vec_rank(p, q, E['bge-m3'])}
for e in PAIRS['pairs']:
    ids = set(ANNOT.get(e['id']) or ()); s = byn.get(e['repeat'])
    if not ids or s is None: continue
    pool = ranking_pool(s); present = ids & {r.claim_id for r in pool}
    if not present: continue
    nongold = [r for r in pool if r.claim_id not in present]
    q2[e['id']] = {'pool': len(pool), 'chance_best': round((len(pool) + 1) / (len(present) + 1), 1),
                   'plan_stems_shared_with_nongold_mean': round(mean(len(stems(s.plan_text) & stems(r.text)) for r in nongold), 1),
                   **{f'repeat/{n}': best_rank(f(pool, e['repeat_words']), present) for n, f in rk2.items()},
                   **{f'first/{n}': best_rank(f(pool, e['first_words']), present) for n, f in rk2.items()}}
out['check2_repeat_wording'] = q2
print(json.dumps(out, indent=1, default=str))
