from memory_bench.ranking import pair_ranks, ranking_pool
from tests.retrieval_bench.helpers import rec, scene


def ranker_of(order):
    def rank(candidates, query):
        by_id = {r.claim_id: r for r in candidates}
        return [by_id[i] for i in order if i in by_id]
    return rank


def pool_scene(n=30, number=5, plan='план'):
    records = [rec(f'r{i}', 'facts', f'факт {i}') for i in range(n)] + [rec('tl', 'timeline', 'подія', kind='timeline')]
    return scene(records, number=number, plan=plan)


def test_ranking_pool_excludes_timeline():
    s = pool_scene(3)
    assert [r.claim_id for r in ranking_pool(s)] == ['r0', 'r1', 'r2']


def test_pair_ranks_recall_at_k():
    s = pool_scene()
    out = pair_ranks({'bm25': ranker_of([f'r{i}' for i in range(30)])}, {'p1': ['r6']},
                     {'pairs': [{'id': 'p1', 'repeat': 5}], 'controls': []}, {5: s})
    res = out['bm25']['pair']
    assert res == {'recall_at': {'5': 0, '10': 1, '20': 1}, 'total': 1, 'median_rank': 7.0}
    assert out['bm25']['control'] == {'recall_at': {'5': 0, '10': 0, '20': 0}, 'total': 0, 'median_rank': None}
    assert 'r6' not in str(out)


def test_unranked_record_counts_as_miss():
    s = pool_scene()
    out = pair_ranks({'bm25': ranker_of(['r1'])}, {'p1': ['r6'], 'p2': ['r1']},
                     {'pairs': [{'id': 'p1', 'repeat': 5}, {'id': 'p2', 'repeat': 5}], 'controls': []}, {5: s})
    assert out['bm25']['pair'] == {'recall_at': {'5': 1, '10': 1, '20': 1}, 'total': 2, 'median_rank': 1.0}


def test_pair_ranks_excludes_unannotated_skipped_and_missing():
    s = pool_scene()
    pairs = {'pairs': [{'id': 'a', 'repeat': 5}, {'id': 'b', 'repeat': 99}, {'id': 'c', 'repeat': 5}, {'id': 'd', 'repeat': 5}],
             'controls': []}
    out = pair_ranks({'bm25': ranker_of(['r2', 'r3'])}, {'a': ['r3', 'r2'], 'b': ['r2'], 'c': ['nope'], 'd': ['tl']}, pairs, {5: s})
    assert out['bm25']['pair'] == {'recall_at': {'5': 1, '10': 1, '20': 1}, 'total': 1, 'median_rank': 1.0}
