import json

import pytest

from memory_bench.paraphrase import Query, _sha
from memory_bench.paraphrase_eval import evaluate_paraphrases, rank_of, sign_test, stale_queries
from memory_bench.strategies import Params, fts_rank, structural_fts
from tests.retrieval_bench.helpers import rec, scene

TARGET = 'Ключ лежить у бляшанці під лавою'
OTHERS = ['Маяк стоїть на скелі біля води', 'Човен гниє на березі', 'Сад обріс бур’янами', 'Годинник зупинився вночі']
PLAN = 'Марія іде вздовж берега'


def records(source=1):
    return [rec('t1', 'facts', TARGET, scene=source)] + [rec(f'o{i}', 'facts', t, scene=source) for i, t in enumerate(OTHERS)]


def world(source=1, later=2):
    """Scene `source` holds the records; scene `later` (when set) repeats them under a plan."""
    scenes = [scene(records(source), id=f's{source}', number=source)]
    if later:
        scenes.append(scene(records(source), id=f's{later}', number=later, plan=PLAN))
    return scenes


def q(level, text, status='ok', claim='t1', source=TARGET):
    return Query(claim, level, text, status, _sha(source))


def params_of(budget, core):
    return Params(budget, 'realistic', core)


RANKERS = {'bm25': fts_rank}
STRATEGIES = {'structural_fts': structural_fts}


def run(queries, scenes=None, **kw):
    return evaluate_paraphrases(scenes or world(), queries, kw.pop('rankers', RANKERS), kw.pop('strategies', STRATEGIES),
                                params_of, **kw)


def test_rank_of_none_when_not_returned():
    assert rank_of('x', [rec('a', 'facts', 'щось')]) is None


def test_rank_of_is_one_based():
    assert rank_of('b', [rec('a', 'facts', 'x'), rec('b', 'facts', 'y')]) == 2


def test_sign_test_none_is_worst():
    r = sign_test([1, None, 3], [None, None, 5])
    assert (r['a_better'], r['b_better'], r['ties']) == (2, 0, 1)


def test_sign_test_matches_offline_checks():
    import math
    a, b = [1, 2, 3, 9, 4, 8, 7, 2], [2, 1, 5, 3, 9, 1, 2, 4]
    wa, wb = sum(x < y for x, y in zip(a, b)), sum(x > y for x, y in zip(a, b))
    n, k = wa + wb, min(wa, wb)  # the arithmetic of adhoc_2026_11_25/offline_checks.sign_test, spelled out
    expected = round(min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n), 4)
    r = sign_test(a, b)
    assert (r['a_better'], r['b_better'], r['ties'], r['p']) == (wa, wb, len(a) - n, expected)
    assert sign_test([1, 1], [1, 1]) == {'a_better': 0, 'b_better': 0, 'ties': 2, 'p': 1.0}
    assert sign_test([1] * 5, [2] * 5)['p'] == 0.0625


def test_bm25_without_overlap_counts_as_not_found():
    out = run([q('syn', 'Абракадабра зовсім інша історія')])['syn']['bm25']
    assert out['n'] == 1 and out['standalone']['found'] == 0 and out['standalone']['top5'] == 0
    assert out['standalone']['median_rank'] is None and out['in_plan']['found'] == 0


def test_found_target_is_ranked_first_in_both_forms():
    out = run([q('same', 'ключ у бляшанці під лавою')])['same']['bm25']
    assert out['standalone']['median_rank'] == 1.0 and out['standalone']['top5'] == 1.0
    assert out['in_plan']['median_rank'] == 1.0 and out['in_plan']['no_scene'] == 0


def test_in_plan_without_later_scene_goes_to_no_scene():
    out = run([q('same', 'ключ у бляшанці')], scenes=world(source=5, later=None))['same']['bm25']
    assert out['in_plan']['no_scene'] == 1 and out['in_plan']['found'] == 0
    assert out['standalone']['found'] == 1.0  # the frame holds the record: standalone still works


def test_in_plan_pool_excludes_layered_records():
    layered = rec('lay', 'facts', 'Марія ключ бляшанці під лавою ключ ключ', scene=1)
    scenes = [scene(records() + [layered], id='s1', number=1), scene(records() + [layered], id='s2', number=2, plan='Марія')]
    out = run([q('same', 'ключ бляшанці під лавою')], scenes=scenes)['same']['bm25']
    assert out['in_plan']['median_rank'] == 1.0


def test_rejected_and_unreliable():
    ok = [q('syn', 'ключ бляшанці')] * 4
    out = run(ok + [q('syn', 'ключ', status='rejected')])['syn']['bm25']
    assert out['n'] == 4 and out['rejected'] == 1 and out['unreliable'] is True  # 1 / 5 > 0.10
    clean = run(ok + [q('syn', 'ключ')])['syn']['bm25']
    assert clean['n'] == 5 and clean['rejected'] == 0 and clean['unreliable'] is False
    only_rejected = run([q('same', 'x', status='rejected')])['same']['bm25']
    assert only_rejected['n'] == 0 and only_rejected['rejected'] == 1 and only_rejected['unreliable'] is True


def test_boundary_ten_percent_is_reliable():
    ok = [q('desc', 'ключ бляшанці')] * 9
    assert run(ok + [q('desc', 'k', status='rejected')])['desc']['bm25']['unreliable'] is False  # exactly 1 / 10


def test_in_context_uses_budget_steps_and_both_cores():
    filler = [rec(f'f{i}', 'facts', f'Окремий запис номер {i} ' + 'слово ' * 30, scene=1) for i in range(30)]
    scenes = [scene(records() + filler, id='s1', number=1),
              scene(records() + filler, id='s2', number=2, plan=PLAN)]
    out = run([q('same', 'ключ бляшанці під лавою')], scenes=scenes, steps=(1.0, 0.01))['same']['bm25']
    ctx = out['in_plan']['in_context']
    assert set(ctx) == {'1.0', '0.01'} and set(ctx['1.0']) == {'upper', 'lower'}
    assert ctx['1.0'] == {'upper': 1.0, 'lower': 1.0}
    assert ctx['0.01'] == {'upper': 0.0, 'lower': 0.0}
    assert set(run([q('same', 'ключ')])['same']['bm25']['in_plan']['in_context']) == {'0.75', '0.5', '0.35'}


def test_in_context_query_is_plan_plus_paraphrase():
    seen = []

    def spy(sc, params):
        seen.append(sc.plan_text)
        return structural_fts(sc, params)
    run([q('same', 'ключ бляшанці')], strategies={'structural_fts': spy})
    assert seen and all(t == f'{PLAN} ключ бляшанці' for t in seen)


def test_stale_queries():
    scenes = world()
    assert not stale_queries([q('same', 'x')], scenes)
    assert stale_queries([q('same', 'x', claim='gone')], scenes)
    assert stale_queries([q('same', 'x', source='Інший текст запису')], scenes)
    assert stale_queries([Query('t1', 'same', 'x', 'rejected', '')], scenes)  # rejected queries are checked too


def test_no_texts_in_result():
    out = json.dumps(run([q('same', 'ключ бляшанці під лавою'), q('syn', 'x', status='rejected')]), ensure_ascii=False)
    for text in [TARGET, 'ключ бляшанці під лавою', PLAN, *OTHERS]:
        assert text not in out


def test_vector_columns_and_sign_vs_bm25():
    pytest.importorskip('numpy')
    from memory_bench.embeddings import FakeEmbedder
    from memory_bench.ranking import rrf_rank, vec_rank
    from memory_bench.strategies import vector_strategies
    e = FakeEmbedder()
    e.key = 'fake'
    rankers = {'bm25': fts_rank, 'vec[fake]': lambda p, t: vec_rank(p, t, e), 'hybrid[fake]': lambda p, t: rrf_rank(p, t, e)}
    out = run([q('same', 'ключ бляшанці під лавою'), q('same', 'сад бурʼяни', claim='o2', source=OTHERS[2])],
              rankers=rankers, strategies={'structural_fts': structural_fts, **vector_strategies(e)})['same']
    assert set(out) == {'bm25', 'vec[fake]', 'hybrid[fake]'} and 'sign_vs_bm25' not in out['bm25']
    for column in ('vec[fake]', 'hybrid[fake]'):
        assert set(out[column]['sign_vs_bm25']) == {'standalone', 'in_plan'}
        assert set(out[column]['sign_vs_bm25']['standalone']) == {'a_better', 'b_better', 'ties', 'p'}
        assert out[column]['n'] == 2 and out[column]['standalone']['found'] == 1.0  # vectors return every record
