import json, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from offline_checks import *  # noqa
from memory_bench.strategies import _structural_retrieval
repo = Repository(DATA)
st = max(repo.list_stories(), key=lambda s: (len(repo.list_scenes(s.id)), s.id))
sc, _ = extract_story(repo, st.id)
tot = {s.scene_id: full(s, Params(10**12, 'realistic', 'upper')).tokens_realistic for s in sc}
tq = {s.plan_text: s for s in sc}
def oracle(p, q):
    g = tq[q].targets; base = fts_rank(p, q); rest = [r for r in p if r not in base]
    return [r for r in p if r.claim_id in g] + [r for r in base + rest if r.claim_id not in g]
E = {k: embedder(k) for k in ('e5-base', 'bge-m3')}
rk = {'fts': fts_rank, 'oracle': oracle}
for k, e in E.items():
    rk[f'vec[{k}]'] = lambda p, q, e=e: vec_rank(p, q, e)
    rk[f'hybrid[{k}]'] = lambda p, q, e=e: rrf_rank(p, q, e)
    rk[f'maxsim[{k}]'] = lambda p, q, e=e: maxsim_rank(p, q, e)
out = {}
for step in (0.9, 0.75, 0.6, 0.5, 0.42, 0.35):
    for mode in ('upper', 'lower'):
        row = {}
        for n, r in rk.items():
            strat = _structural_retrieval(n, 'fts', r)
            sels = [strat(s, Params(int(step * tot[s.scene_id]), 'realistic', mode)) for s in sc]
            a = aggregate([scene_metrics(s, x) for s, x in zip(sc, sels)], sels)
            row[n] = (round(a['target_recall'] * a['targets_total']), round(a['target_recall_core'] * 39 if a['target_recall_core'] else 0, 1), a['target_recall_atmosphere'], a['chars']['mean'])
        out[f'{step}/{mode}'] = row
print(json.dumps(out, indent=1))
