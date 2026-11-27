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


# ---- F2: capped-rank sign test, paired in-context test, raw rank secondary ------------------------------------------

def _dummies(n):
    return [rec(f'd{i}', 'facts', f'заповнювач {i}') for i in range(n)]


def _at(place):
    """A ranker that puts the target of the query at `place` (None: never returns it)."""
    def ranker(pool, text):
        target = [r for r in pool if r.claim_id in text.split()]
        return _dummies(80) if place is None else _dummies(place - 1) + target
    return ranker


def _two_targets():
    return [q('same', 't1 ключ бляшанці'), q('same', 'o0 маяк скеля', claim='o0', source=OTHERS[0])]


def test_sign_vs_bm25_caps_ranks_at_k_plus_one():
    from memory_bench.paraphrase_eval import CAP_K
    assert CAP_K == 10
    out = run(_two_targets(), rankers={'bm25': _at(None), 'vec[d]': _at(80)},
              strategies={'structural_fts': structural_fts, 'structural_vec[d]': structural_fts})['same']['vec[d]']
    # rank 80 against "not returned" is a tie once both are capped at K + 1 = 11; the raw test still calls it a win
    assert out['sign_vs_bm25']['standalone'] == {'a_better': 0, 'b_better': 0, 'ties': 2, 'p': 1.0}
    assert out['sign_vs_bm25_raw']['standalone']['a_better'] == 2
    near = run(_two_targets(), rankers={'bm25': _at(None), 'vec[d]': _at(10)},
               strategies={'structural_fts': structural_fts, 'structural_vec[d]': structural_fts})['same']['vec[d]']
    assert near['sign_vs_bm25']['standalone']['a_better'] == 2 and near['sign_vs_bm25']['in_plan']['a_better'] == 2


def test_sign_in_context_vs_bm25_pairs_hits_per_record():
    from types import SimpleNamespace
    keep_all = lambda sc, params: SimpleNamespace(record_ids=tuple(r.claim_id for r in sc.records))
    keep_none = lambda sc, params: SimpleNamespace(record_ids=())
    out = run(_two_targets(), rankers={'bm25': fts_rank, 'vec[d]': fts_rank},
              strategies={'structural_fts': keep_none, 'structural_vec[d]': keep_all})['same']
    test = out['vec[d]']['sign_in_context_vs_bm25']
    assert set(test) == {'0.75', '0.5', '0.35'} and set(test['0.5']) == {'upper', 'lower'}
    assert test['0.5']['upper'] == {'a_better': 2, 'b_better': 0, 'ties': 0, 'p': 0.5}  # more hits wins
    flipped = run(_two_targets(), rankers={'bm25': fts_rank, 'vec[d]': fts_rank},
                  strategies={'structural_fts': keep_all, 'structural_vec[d]': keep_none})['same']['vec[d]']
    assert flipped['sign_in_context_vs_bm25']['0.35']['lower']['b_better'] == 2
    assert 'sign_in_context_vs_bm25' not in out['bm25']


def test_sign_in_context_without_later_scene_is_a_tie():
    from types import SimpleNamespace
    keep_all = lambda sc, params: SimpleNamespace(record_ids=tuple(r.claim_id for r in sc.records))
    out = run(_two_targets(), scenes=world(source=5, later=None), rankers={'bm25': fts_rank, 'vec[d]': fts_rank},
              strategies={'structural_fts': structural_fts, 'structural_vec[d]': keep_all})['same']['vec[d]']
    assert out['sign_in_context_vs_bm25']['0.75']['upper']['ties'] == 2


# ---- F7: rejected by category, targets with fewer than two content words -------------------------------------------

def test_rejected_by_category_and_few_content_words():
    recs = records() + [rec('th', 'open_threads', 'Хто розбив вікно', scene=1), rec('one', 'facts', 'Острів у тумані', scene=1),
                        rec('two', 'open_threads', 'Годинник', scene=1)]
    scenes = [scene(recs, id='s1', number=1), scene(recs, id='s2', number=2, plan=PLAN)]
    qs = [q('syn', 'x', status='rejected'), q('syn', 'y', status='rejected', claim='th', source='Хто розбив вікно'),
          q('syn', 'z', status='rejected', claim='two', source='Годинник'), q('syn', 'Жовтий човник', claim='one', source='Острів у тумані'),
          q('same', 'ключ бляшанці')]
    out = run(qs, scenes=scenes)
    syn = out['syn']['bm25']
    assert syn['rejected_by_category'] == {'facts': 1, 'open_threads': 2} and syn['rejected'] == 3
    # 'Годинник' has one content word and can never pass 'same'; 'Острів у тумані' has two
    assert syn['few_content_words'] == 1
    assert out['same']['bm25']['rejected_by_category'] == {} and out['same']['bm25']['few_content_words'] == 0


# ---- M6: in-context hits when the query is the plan alone -----------------------------------------------------------

def _m6_world():
    filler = [rec(f'f{i}', 'facts', f'Окремий запис номер {i} ' + 'слово ' * 30, scene=1) for i in range(30)]
    return [scene(records() + filler, id='s1', number=1), scene(records() + filler, id='s2', number=2, plan=PLAN)]


def test_paraphrase_baseline_plan():
    from memory_bench.paraphrase_eval import evaluate_baseline_plan
    scenes = _m6_world()
    qs = [q('same', ''), q('syn', ''), q('desc', 'x', status='rejected')]
    base = evaluate_baseline_plan(scenes, qs, ['bm25'], STRATEGIES, params_of, steps=(1.0, 0.01))
    assert base['n'] == {'same': 1, 'syn': 1, 'desc': 0}  # each level's ok queries: the population of its in_context
    assert set(base['levels']) == {'same', 'syn', 'desc'} and set(base['levels']['same']) == {'bm25'}
    assert set(base['levels']['same']['bm25']) == {'1.0', '0.01'} and set(base['levels']['same']['bm25']['1.0']) == {'upper', 'lower'}
    ctx = run(qs[:1], scenes=scenes, steps=(1.0, 0.01))['same']['bm25']['in_plan']['in_context']
    assert base['levels']['same']['bm25'] == ctx  # an empty paraphrase sentence leaves the plan alone
    assert base['levels']['desc']['bm25']['1.0'] == {'upper': 0.0, 'lower': 0.0}
    seen = []

    def spy(sc, params):
        seen.append(sc.plan_text)
        return structural_fts(sc, params)
    evaluate_baseline_plan(scenes, qs, ['bm25'], {'structural_fts': spy}, params_of)
    assert seen and set(seen) == {PLAN} and len(seen) == 3 * 2  # once per record, not per level: 3 steps x 2 cores


def test_baseline_plan_is_aggregated_over_each_level_population():
    """A record rejected in one level is absent from that level's baseline, like from its in_context."""
    from memory_bench.paraphrase_eval import evaluate_baseline_plan, plan_only_hits
    scenes = _m6_world()
    qs = [q('same', 'ключ'), q('syn', 'ключ'), q('same', 'маяк', claim='o0', source=OTHERS[0]),
          q('syn', 'маяк', status='rejected', claim='o0', source=OTHERS[0])]
    hits = {'bm25': {'t1': {'0.5': {'upper': 1, 'lower': 1}}, 'o0': {'0.5': {'upper': 0, 'lower': 1}}}}
    base = evaluate_baseline_plan(scenes, qs, ['bm25'], STRATEGIES, params_of, steps=(0.5,), hits=hits)
    assert base['n'] == {'same': 2, 'syn': 1, 'desc': 0}
    assert base['levels']['same']['bm25']['0.5'] == {'upper': 0.5, 'lower': 1.0}
    assert base['levels']['syn']['bm25']['0.5'] == {'upper': 1.0, 'lower': 1.0}
    computed = plan_only_hits(scenes, qs, ['bm25'], STRATEGIES, params_of, steps=(0.5,))
    assert set(computed['bm25']) == {'t1', 'o0'} and set(computed['bm25']['t1']['0.5']) == {'upper', 'lower'}


def test_baseline_plan_without_later_scene_is_a_miss():
    from memory_bench.paraphrase_eval import evaluate_baseline_plan
    base = evaluate_baseline_plan(world(source=5, later=None), [q('same', 'ключ')], ['bm25'], STRATEGIES, params_of)
    assert base['n']['same'] == 1 and base['levels']['same']['bm25']['0.75'] == {'upper': 0.0, 'lower': 0.0}
    assert evaluate_baseline_plan(world(), [], ['bm25'], STRATEGIES, params_of)['n'] == {'same': 0, 'syn': 0, 'desc': 0}


def test_sign_in_context_vs_plan_pairs_records_per_level():
    from types import SimpleNamespace
    keep_all = lambda sc, params: SimpleNamespace(record_ids=tuple(r.claim_id for r in sc.records))
    qs = _two_targets()
    plan_none = {'bm25': {c: {s: {'upper': 0, 'lower': 0} for s in ('0.75', '0.5', '0.35')} for c in ('t1', 'o0')}}
    out = run(qs, strategies={'structural_fts': keep_all}, plan_hits=plan_none)['same']['bm25']
    test = out['sign_in_context_vs_plan']
    assert set(test) == {'0.75', '0.5', '0.35'} and set(test['0.5']) == {'upper', 'lower'}
    assert test['0.5']['upper'] == {'a_better': 2, 'b_better': 0, 'ties': 0, 'p': 0.5}  # in_plan hits, plan-only misses
    plan_all = {'bm25': {c: {s: {'upper': 1, 'lower': 1} for s in ('0.75', '0.5', '0.35')} for c in ('t1', 'o0')}}
    same = run(qs, strategies={'structural_fts': keep_all}, plan_hits=plan_all)['same']['bm25']
    assert same['sign_in_context_vs_plan']['0.35']['lower'] == {'a_better': 0, 'b_better': 0, 'ties': 2, 'p': 1.0}
    assert 'sign_in_context_vs_plan' not in run(qs)['same']['bm25']  # only when the caller passes the plan-only hits
