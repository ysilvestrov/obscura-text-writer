import pytest

np = pytest.importorskip('numpy')

from memory_bench.embeddings import FakeEmbedder
from memory_bench.strategies import LAYERS, STRATEGIES, Params, vector_strategies
from tests.retrieval_bench.helpers import rec, rich_records, scene


def params(**kw):
    base = dict(memory_budget_tokens=100000, measure='conservative', core_mode='upper')
    return Params(**{**base, **kw})


class Pinned(FakeEmbedder):
    """Fake vectors, except that listed texts get a fixed vector."""

    def __init__(self, table):
        super().__init__(dim=4)
        self.table = table

    def embed(self, texts, kind):
        base = super().embed(texts, kind)
        for i, t in enumerate(texts):
            if t in self.table:
                vec = np.array(self.table[t], dtype=np.float32)
                base[i] = vec / np.linalg.norm(vec)
        return base


def test_strategies_not_registered_globally():
    assert 'structural_vec' not in STRATEGIES and 'vec' in LAYERS and 'hybrid' in LAYERS


def test_keys_carry_embedder_key():
    assert set(vector_strategies(FakeEmbedder())) == {'structural_vec[fake]', 'structural_hybrid[fake]'}


def test_vec_strategy_same_pool_and_budget_as_fts():
    s = scene(rich_records(), plan='маяк на скелі')
    for n in (800, 1500, 3000, 100000):
        p = params(memory_budget_tokens=n)
        fts = STRATEGIES['structural_fts'](s, p)
        vec = vector_strategies(FakeEmbedder())['structural_vec[fake]'](s, p)
        assert fts.overflow == vec.overflow
        assert fts.dropped_by_budget == vec.dropped_by_budget
        skip = ('fts', 'vec')
        assert {k: v for k, v in fts.layers.items() if k not in skip} == {k: v for k, v in vec.layers.items() if k not in skip}
        base = set(STRATEGIES['structural'](s, p).record_ids)
        assert base <= set(vec.record_ids) and base <= set(fts.record_ids)
        assert set(vec.record_ids) - base == set(vec.retrieval_ids)
        assert len(vec.retrieval_ids) == vec.layers['vec'] and vec.layers['fts'] == 0


def test_vec_strategy_picks_semantic_match_with_fake():
    s = scene(rich_records(), plan='запит без збігів слів')
    emb = Pinned({'запит без збігів слів': [1, 0, 0, 0], 'Хтось бачив вовка': [1, 0, 0, 0]})
    sel = vector_strategies(emb)['structural_vec[fake]'](s, params())
    assert sel.retrieval_ids and sel.retrieval_ids[0] == 'thr_far'


def test_hybrid_layer_name():
    s = scene(rich_records(), plan='маяк на скелі')
    sel = vector_strategies(FakeEmbedder())['structural_hybrid[fake]'](s, params())
    assert sel.strategy == 'structural_hybrid[fake]'
    assert sel.layers['hybrid'] > 0 and sel.layers['vec'] == 0 and sel.layers['fts'] == 0
    assert len(sel.retrieval_ids) == sel.layers['hybrid']


def test_vec_empty_plan_adds_nothing_and_never_timeline():
    records = rich_records() + [rec('tl1', 'timeline', 'Маяк на скелі горів')]
    strategy = vector_strategies(FakeEmbedder())['structural_vec[fake]']
    assert strategy(scene(records, plan=''), params()).retrieval_ids == ()
    assert 'tl1' not in strategy(scene(records, plan='маяк'), params()).record_ids
