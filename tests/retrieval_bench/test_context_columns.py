"""Contextual retrieval columns (Voyage bench #25, task 4): rankers search over `context + record text`, while the budget,
record_ids and the rendered memory use the original records only."""
import json
import pytest

from memory_bench.context_gen import CONTEXT_PROMPT_ID, HAIKU, context_key, context_snapshot, context_targets
from memory_bench.ranking import contextual, contextual_versions
from memory_bench.strategies import Params, context_strategies, fts_rank, structural_fts
from tests.retrieval_bench.helpers import rec, rich_records, scene

SENTINEL = 'Квазиморфія'  # a word only the fake contexts carry


def _bench():
    import memory_retrieval_bench
    return memory_retrieval_bench


def params(budget=100000, measure='conservative', core='upper'):
    return Params(budget, measure, core)


def test_contextual_ranks_by_search_text_returns_originals():
    pool = [rec('a', 'facts', 'Маяк стоїть на скелі'), rec('b', 'facts', 'Човен гниє на березі')]
    assert fts_rank(pool, 'бляшанка') == []
    ranked = contextual(fts_rank, {'b': 'Бляшанка під лавою\nЧовен гниє на березі'})(pool, 'бляшанка')
    assert [r.claim_id for r in ranked] == ['b'] and ranked[0] is pool[1]
    both = contextual(fts_rank, {'a': 'маяк маяк маяк\nМаяк стоїть на скелі'})(pool, 'маяк човен')
    assert all(any(r is p for p in pool) for r in both) and both[0] is pool[0]


def test_contextual_versions_picks_the_text_version_of_the_pool():
    old, new = rec('s', 'character_states', 'Марія в халаті'), rec('s', 'character_states', 'Марія без халата')
    versions = {('s', old.text): f'бляшанка\n{old.text}', ('s', new.text): f'човен\n{new.text}'}
    ranker = contextual_versions(fts_rank, versions)
    assert ranker([old], 'бляшанка') == [old] and ranker([old], 'човен') == []
    assert ranker([new], 'човен') == [new] and ranker([new], 'бляшанка') == []


def test_ctx_strategy_with_empty_contexts_equals_plain_column():
    s = scene(rich_records(), plan='маяк на скелі')
    ctx = context_strategies({}, [])
    assert set(ctx) == {'structural_ctx_fts'}
    for budget in (100000, 900, 400):
        for core in ('upper', 'lower'):
            plain, mine = structural_fts(s, params(budget, core=core)), ctx['structural_ctx_fts'](s, params(budget, core=core))
            assert mine.record_ids == plain.record_ids and mine.retrieval_ids == plain.retrieval_ids
            assert mine.layers['ctx_fts'] == plain.layers['fts'] and mine.layers['fts'] == 0
            assert {k: v for k, v in mine.layers.items() if k not in ('fts', 'ctx_fts')} == \
                   {k: v for k, v in plain.layers.items() if k not in ('fts', 'ctx_fts')}
            assert (mine.chars, mine.tokens_conservative, mine.dropped_by_budget) == \
                   (plain.chars, plain.tokens_conservative, plain.dropped_by_budget)


def test_ctx_budget_uses_record_text_only():
    records = rich_records()
    s = scene(records, plan='маяк на скелі')
    # a long context on every record keeps the BM25 order (same word repeated for all) but would blow any budget
    versions = {(r.claim_id, r.text): 'довгий ' * 400 + '\n' + r.text for r in records}
    ctx = context_strategies(versions, [])['structural_ctx_fts']
    order = [r.claim_id for r in contextual_versions(fts_rank, versions)(records, s.plan_text)]
    assert order == [r.claim_id for r in fts_rank(records, s.plan_text)]  # the precondition: equal ranking order
    for budget in (1200, 900):
        plain, mine = structural_fts(s, params(budget)), ctx(s, params(budget))
        assert mine.retrieval_ids and mine.record_ids == plain.record_ids
        assert mine.tokens_conservative == plain.tokens_conservative and not mine.overflow
        from memory_bench.model import render
        by_id = {r.claim_id: r for r in records}
        chosen = [by_id[c] for c in mine.record_ids]
        assert mine.chars == len(render(chosen, [], 0)) and 'довгий' not in render(chosen, [], 0)


def test_ctx_vector_strategies_per_embedder():
    pytest.importorskip('numpy')
    from memory_bench.embeddings import FakeEmbedder
    e = FakeEmbedder()
    e.key = 'm'
    ctx = context_strategies({}, [e])
    assert set(ctx) == {'structural_ctx_fts', 'structural_ctx_vec[m]', 'structural_ctx_hybrid[m]'}
    s = scene(rich_records(), plan='маяк на скелі')
    from memory_bench.strategies import vector_strategies
    plain = vector_strategies(e)
    for kind in ('vec', 'hybrid'):
        mine, base = ctx[f'structural_ctx_{kind}[m]'](s, params(900)), plain[f'structural_{kind}[m]'](s, params(900))
        assert mine.record_ids == base.record_ids and mine.layers[f'ctx_{kind}'] == base.layers[kind] > 0


def test_ctx_hybrid_fuses_contextual_bm25_and_vector():
    pytest.importorskip('numpy')
    from memory_bench.embeddings import FakeEmbedder
    e = FakeEmbedder()
    e.key = 'm'
    pool = [rec(f'r{i}', 'facts', f'Окремий запис {i}') for i in range(6)]
    versions = {('r3', pool[3].text): f'{SENTINEL}\n{pool[3].text}'}
    seen = []

    class Spy(FakeEmbedder):
        def embed(self, texts, kind):
            seen.extend(texts)
            return super().embed(texts, kind)
    spy = Spy()
    spy.key = 'm'
    s = scene(pool, plan=SENTINEL)
    sel = context_strategies(versions, [spy])['structural_ctx_hybrid[m]'](s, params())
    assert any(SENTINEL in t for t in seen)  # the vector part embeds the search text
    assert sel.retrieval_ids[0] == 'r3'  # BM25 over the context matched only r3, so it leads the fusion


# ---- load_contexts -------------------------------------------------------------------------------------------------

def _scenes():
    a, b = rec('a', 'facts', 'Маяк стоїть на скелі', scene=1), rec('b', 'facts', 'Човен гниє на березі', scene=1)
    s_old = rec('s', 'character_states', 'Марія в халаті', ['c1'], scene=1)
    s_new = rec('s', 'character_states', 'Марія без халата', ['c1'], scene=2)
    orphan = rec('n', 'facts', 'Годинник зупинився', scene=None)
    first = scene([a, b, s_old], id='s1', number=1, prose='Проза першої сцени')
    second = scene([a, b, s_new, orphan], id='s2', number=2, prose='Проза другої сцени')
    return [first, second]


def write_contexts(folder, scenes, story='story', failed=(), drop=(), meta_over=None, snapshot=None):
    """contexts.json the way scripts/rag_contexts.py writes it: every target 'ok' with a context carrying SENTINEL,
    except claim_ids in `failed`; `drop` removes items by claim_id."""
    targets, _ = context_targets(scenes)
    items = {}
    for record, prose in targets:
        if record.claim_id in drop:
            continue
        item = {'claim_id': record.claim_id, 'source_scene': record.source_scene,
                'status': 'failed' if record.claim_id in failed else 'ok'}
        if item['status'] == 'ok':
            item['context'] = f'{SENTINEL} {record.claim_id} {record.source_scene}'
        items[context_key(record, prose)] = item
    meta = {'model': HAIKU, 'prompt_id': CONTEXT_PROMPT_ID, 'story': story, 'prices_date': '2026-11-27', **(meta_over or {})}
    data = {'meta': meta, 'items': items, 'snapshot': snapshot or context_snapshot(items)}
    (folder / 'contexts.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return data


def test_load_contexts_codes(outside_dir):
    load = _bench().load_contexts
    scenes = _scenes()
    from pathlib import Path
    assert load(Path(__file__).parent, scenes, 'story') == (None, None, 'inside_repo')
    assert load(outside_dir, scenes, 'story') == (None, None, 'contexts_missing')
    (outside_dir / 'contexts.json').write_text('{"meta": 1', encoding='utf-8')
    assert load(outside_dir, scenes, 'story') == (None, None, 'contexts_missing')
    write_contexts(outside_dir, scenes, story='other')
    assert load(outside_dir, scenes, 'story') == (None, None, 'contexts_stale')
    for field in ('prompt_id', 'model'):
        write_contexts(outside_dir, scenes, meta_over={field: 'x'})
        assert load(outside_dir, scenes, 'story') == (None, None, 'contexts_stale')
    write_contexts(outside_dir, scenes, drop=('b',))
    assert load(outside_dir, scenes, 'story') == (None, None, 'contexts_stale')
    write_contexts(outside_dir, scenes, snapshot='0' * 64)
    assert load(outside_dir, scenes, 'story') == (None, None, 'contexts_stale')
    data = write_contexts(outside_dir, scenes)
    next(iter(data['items'].values())).pop('context')  # an 'ok' item without its context
    (outside_dir / 'contexts.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    assert load(outside_dir, scenes, 'story') == (None, None, 'contexts_stale')
    data = write_contexts(outside_dir, scenes)
    for item in data['items'].values():
        if item['claim_id'] == 'b':
            item['status'] = 'truncated'  # neither 'ok' nor 'failed': never mixed in silently
    data['snapshot'] = context_snapshot(data['items'])
    (outside_dir / 'contexts.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    assert load(outside_dir, scenes, 'story') == (None, None, 'contexts_stale')
    write_contexts(outside_dir, scenes, failed=('b',))
    search, section, error = load(outside_dir, scenes, 'story')
    assert error is None and section['ok'] == 3 and section['failed'] == 1 and section['no_source'] == 1
    assert ('b', 'Човен гниє на березі') not in search  # a failed record is searched by its own text
    assert search[('a', 'Маяк стоїть на скелі')] == f'{SENTINEL} a 1\nМаяк стоїть на скелі'
    assert len(section['snapshot']) == 64 and SENTINEL not in json.dumps(section, ensure_ascii=False)


def test_load_contexts_keeps_each_text_version_of_a_claim(outside_dir):
    """An updated claim has two texts (and two source scenes): each version is searched with its own context."""
    scenes = _scenes()
    write_contexts(outside_dir, scenes)
    search, _, error = _bench().load_contexts(outside_dir, scenes, 'story')
    assert error is None
    assert search[('s', 'Марія в халаті')].startswith(f'{SENTINEL} s 1\n')
    assert search[('s', 'Марія без халата')].startswith(f'{SENTINEL} s 2\n')


def test_no_source_record_uses_own_text(outside_dir):
    scenes = _scenes()
    write_contexts(outside_dir, scenes)
    search, section, error = _bench().load_contexts(outside_dir, scenes, 'story')
    assert error is None and section['no_source'] == 1
    assert ('n', 'Годинник зупинився') not in search
    orphan = next(r for r in scenes[1].records if r.claim_id == 'n')
    ranked = contextual_versions(fts_rank, search)([orphan], 'годинник')
    assert ranked == [orphan]  # its search text is the record itself


# ---- registration --------------------------------------------------------------------------------------------------

def test_ctx_names_registered():
    bench = _bench()
    extra = {'structural_ctx_fts': None, 'structural_ctx_vec[m]': None, 'structural_ctx_hybrid[m]': None}
    keys = {key: (name, mode) for key, name, mode in bench.variants(extra)}
    for name in extra:
        assert keys[f'{name}[core=upper]'] == (name, 'upper') and keys[f'{name}[core=lower]'] == (name, 'lower')
    assert bench.retrieval_layer('structural_ctx_fts') == 'ctx_fts'
    assert bench.retrieval_layer('structural_ctx_vec[m]') == 'ctx_vec'
    assert bench.retrieval_layer('structural_ctx_hybrid[m]') == 'ctx_hybrid'
    assert bench.retrieval_layer('structural_vec[m]') == 'vec' and bench.retrieval_layer('structural_fts') == 'fts'
    assert bench.CTX_MODELS == ('nano-2048', 'voyage-4')
    from memory_bench.paraphrase_eval import strategy_name
    assert strategy_name('ctx_bm25') == 'structural_ctx_fts' and strategy_name('ctx_vec[m]') == 'structural_ctx_vec[m]'
    assert strategy_name('ctx_hybrid[m]') == 'structural_ctx_hybrid[m]' and strategy_name('bm25') == 'structural_fts'
