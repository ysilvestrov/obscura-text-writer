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


def test_rrf_combines_ranks_with_k60():
    pytest.importorskip('numpy')
    from memory_bench.ranking import rrf_rank
    from memory_bench.strategies import fts_rank
    # BM25 order: A (more query words) before B; vector order: B before A. Third record only in vector.
    cands = [rec('A', 'facts', 'маяк скеля море'), rec('B', 'facts', 'маяк'), rec('C', 'facts', 'щось інше')]
    query = 'маяк скеля море'
    assert [r.claim_id for r in fts_rank(cands, query)] == ['A', 'B']
    table = {query: [1, 0, 0], 'маяк скеля море': [1, 0, 0], 'маяк': [0.99, 0.1, 0], 'щось інше': [0, 1, 0]}
    # same text for query and A: A cosine 1.0, B ~0.995, C 0 -> vector order A, B, C
    out = rrf_rank(cands, query, _embedder_of(table))
    assert [r.claim_id for r in out] == ['A', 'B', 'C']
    table['маяк скеля море'] = [0.5, 0.8, 0]
    table[query] = [0.99, 0.1, 0]
    # now vector favours B over A (B identical to query); BM25 favours A: tie 1/61+1/62 each -> claim_id
    out = rrf_rank(cands, query, _embedder_of(table))
    assert [r.claim_id for r in out][:2] == ['A', 'B']


def test_rrf_record_missing_from_bm25_gets_vector_part_only():
    pytest.importorskip('numpy')
    from memory_bench.ranking import rrf_rank
    cands = [rec('only_vec', 'facts', 'zzz'), rec('both', 'facts', 'маяк')]
    table = {'маяк': [0.6, 0.8, 0], 'zzz': [1, 0, 0]}
    # query text 'маяк' embeds as [0.6, 0.8, 0]: 'both' is rank 1 in vector and rank 1 in BM25; 'only_vec' rank 2 vector only
    out = rrf_rank(cands, 'маяк', _embedder_of(table))
    assert [r.claim_id for r in out] == ['both', 'only_vec']
    assert rrf_rank(cands, '  ', _embedder_of(table)) == []
