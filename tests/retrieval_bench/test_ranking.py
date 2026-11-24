import pytest
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




def _embedder_of(table, dim=3):
    import numpy
    from memory_bench.embeddings import FakeEmbedder

    class Table(FakeEmbedder):
        def embed(self, texts, kind):
            return numpy.array([table[t] for t in texts], dtype=numpy.float32)

    return Table(dim=dim)


def test_vec_rank_orders_by_cosine_ties_by_claim_id():
    pytest.importorskip('numpy')
    from memory_bench.ranking import vec_rank
    table = {'q': [1, 0, 0], 'near': [1, 0, 0], 'twin_b': [0, 1, 0], 'twin_a': [0, 1, 0], 'mid': [0.6, 0.8, 0]}
    cands = [rec('b', 'facts', 'twin_b'), rec('a', 'facts', 'twin_a'), rec('n', 'facts', 'near'), rec('m', 'facts', 'mid')]
    assert [r.claim_id for r in vec_rank(cands, 'q', _embedder_of(table))] == ['n', 'm', 'a', 'b']


def test_vec_rank_empty_query_ranks_nothing():
    pytest.importorskip('numpy')
    from memory_bench.ranking import vec_rank
    assert vec_rank([rec('a', 'facts', 'x')], '   ', _embedder_of({'x': [1, 0, 0]})) == []
    assert vec_rank([], 'q', _embedder_of({})) == []


def test_vec_rank_rounds_scores_to_1e6_before_tie_break():
    pytest.importorskip('numpy')
    import math
    from memory_bench.ranking import vec_rank
    x = 5e-4  # cosine 1 - 1.25e-7: below the 1e-6 rounding step, so it ties with the exact 1.0
    table = {'q': [1, 0, 0], 'exact': [1, 0, 0], 'close': [math.sqrt(1 - x * x), x, 0]}
    cands = [rec('b', 'facts', 'exact'), rec('a', 'facts', 'close')]
    assert [r.claim_id for r in vec_rank(cands, 'q', _embedder_of(table))] == ['a', 'b']


def _unit(cosine):
    import math
    return [cosine, math.sqrt(1 - cosine * cosine), 0]


def _fused(bm25, vec, k):
    ids = set(bm25) | set(vec)
    score = {i: (1 / (k + bm25.index(i) + 1) if i in bm25 else 0) + (1 / (k + vec.index(i) + 1) if i in vec else 0)
             for i in ids}
    return sorted(ids, key=lambda i: (-score[i], i))


def test_rrf_combines_ranks_with_k60():
    pytest.importorskip('numpy')
    from memory_bench.ranking import rrf_rank, vec_rank
    from memory_bench.strategies import fts_rank
    query = 'маяк скеля море вітер'
    cands = [rec('A', 'facts', 'вітер маяк скеля море'), rec('B', 'facts', 'маяк скеля море туман'),
             rec('C', 'facts', 'маяк скеля дощ туман'), rec('D', 'facts', 'маяк сніг дощ туман')]
    cos = {'A': 0.3, 'B': 0.7, 'C': 0.9, 'D': 0.5}
    table = {'запит': [1, 0, 0], **{r.text: _unit(cos[r.claim_id]) for r in cands}}
    emb = _embedder_of(table)
    bm25 = [r.claim_id for r in fts_rank(cands, query)]
    vec = [r.claim_id for r in vec_rank(cands, 'запит', emb)]
    assert bm25 == ['A', 'B', 'C', 'D'] and vec == ['C', 'B', 'D', 'A']
    table[query] = [1, 0, 0]
    fused = [r.claim_id for r in rrf_rank(cands, query, emb)]
    assert fused == _fused(bm25, vec, 60) == ['C', 'B', 'A', 'D']
    assert fused not in (bm25, vec)
    # exact values: A = 1/61 + 1/64 < B = 2/62 < C = 1/63 + 1/61
    assert 1 / 61 + 1 / 64 < 2 / 62 < 1 / 63 + 1 / 61
    # k matters: with k=1 A overtakes B
    assert [r.claim_id for r in rrf_rank(cands, query, emb, k=1)] == _fused(bm25, vec, 1) == ['C', 'A', 'B', 'D']


def test_rrf_record_missing_from_bm25_gets_vector_part_only():
    pytest.importorskip('numpy')
    from memory_bench.ranking import rrf_rank, vec_rank
    from memory_bench.strategies import fts_rank
    query = 'маяк скеля море'
    cands = [rec('only_vec', 'facts', 'зовсім інше'), rec('both', 'facts', 'море скеля маяк'),
             rec('bm_also', 'facts', 'маяк скеля дощ')]
    cos = {'only_vec': 0.9, 'both': 0.6, 'bm_also': 0.3}
    table = {query: [1, 0, 0], **{r.text: _unit(cos[r.claim_id]) for r in cands}}
    emb = _embedder_of(table)
    assert [r.claim_id for r in fts_rank(cands, query)] == ['both', 'bm_also']
    assert [r.claim_id for r in vec_rank(cands, query, emb)] == ['only_vec', 'both', 'bm_also']
    # only_vec: 1/61 (vector part only); both: 1/62 + 1/61; bm_also: 1/63 + 1/62
    assert [r.claim_id for r in rrf_rank(cands, query, emb)] == ['both', 'bm_also', 'only_vec']
    assert rrf_rank(cands, '  ', emb) == []
