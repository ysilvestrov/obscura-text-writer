import pytest

from memory_bench.strategies import STRATEGIES, Params, mentions
from memory_bench.extract import name_stems
from tests.retrieval_bench.helpers import rec, rich_records, scene


def params(**kw):
    base=dict(memory_budget_tokens=100000,measure='conservative',core_mode='upper')
    return Params(**{**base,**kw})


def measured(sel,p):
    return sel.tokens_conservative if p.measure=='conservative' else sel.tokens_realistic


def test_full_follows_project_memory_cast_filter():
    sel=STRATEGIES['full'](scene(rich_records(),cast=('c2',)),params())
    assert 'pres1' in sel.record_ids and 'gen1' in sel.record_ids
    assert 'core1' not in sel.record_ids and 'absent' not in sel.record_ids and 'fact_far' in sel.record_ids
    assert not sel.overflow and sel.dropped_by_budget==0


def test_all_active_takes_everything():
    records=rich_records()
    assert set(STRATEGIES['all_active'](scene(records,cast=('c2',)),params()).record_ids)=={r.claim_id for r in records}


def test_core_included_even_when_protagonist_not_in_cast():
    s=scene(rich_records(),cast=('c2',))
    sel=STRATEGIES['structural'](s,params())
    assert {'core1','core_old','pres1','gen1','thr1','fact1'}<=set(sel.record_ids)
    assert 'absent' not in sel.record_ids and 'thr_far' not in sel.record_ids and 'fact_far' not in sel.record_ids


def test_core_overflow_keeps_core_and_empties_rest():
    big=[rec(f'core{i}','character_states','Марія '+'дуже '*40,['c1']) for i in range(10)]
    sel=STRATEGIES['structural'](scene(big+rich_records()),params(memory_budget_tokens=300))
    assert sel.overflow and {f'core{i}' for i in range(10)}<=set(sel.record_ids)
    assert set(sel.record_ids)<={f'core{i}' for i in range(10)}|{'core1','core_old'}
    assert sel.dropped_by_budget>0 and sel.chars>0


@pytest.mark.parametrize('measure',['conservative','realistic'])
@pytest.mark.parametrize('name',['structural','structural_fts'])
def test_budget_never_exceeded_without_overflow(name,measure):
    s=scene(rich_records(),plan='Маяк і море біля скелі')
    for n in (500,800,1500,3000,8000):
        p=params(memory_budget_tokens=n,measure=measure)
        sel=STRATEGIES[name](s,p)
        assert sel.overflow or measured(sel,p)<=n


def test_core_lower_moves_old_states_and_hero_only_facts_to_atmosphere():
    s=scene(rich_records(),cast=('c1','c2'))
    upper=STRATEGIES['structural'](s,params())
    lower=STRATEGIES['structural'](s,params(core_mode='lower',atmosphere_share=0.0))
    assert 'core_old' in upper.record_ids and 'fact_hero' in upper.record_ids
    assert 'core_old' not in lower.record_ids and 'fact_hero' not in lower.record_ids and 'core1' in lower.record_ids
    with_atm=STRATEGIES['structural'](s,params(core_mode='lower',atmosphere_share=0.5))
    assert {'core_old','fact_hero'}<=set(with_atm.record_ids) and with_atm.layers['atmosphere']==2


def test_atmosphere_rotation_deterministic_and_varies_between_scenes():
    atm=[rec(f'old{i}','character_states',f'Марія любить річ {i}',['c1'],1) for i in range(40)]
    p=params(core_mode='lower',memory_budget_tokens=4000,atmosphere_share=0.1)
    a=STRATEGIES['structural'](scene(atm,id='s1'),p)
    b=STRATEGIES['structural'](scene(atm,id='s1'),p)
    c=STRATEGIES['structural'](scene(atm,id='s2'),p)
    assert a==b and 0<a.layers['atmosphere']<40 and set(a.record_ids)!=set(c.record_ids)


def test_mentions_inflected_name_and_short_name():
    assert mentions(rec('x','facts','Бачили Марію вчора'),name_stems('Марія'))
    assert not mentions(rec('x','facts','Ія прийшла'),name_stems('Ія'))
    assert mentions(rec('x','facts','Мар’яну кликали'),name_stems("Мар'яна"))
    assert not mentions(rec('x','facts','Прімарія'),name_stems('Марія'))  # word start only


def test_fts_fills_remainder_and_is_deterministic():
    s=scene(rich_records(),plan='маяк на скелі')
    b=STRATEGIES['structural'](s,params())
    c=STRATEGIES['structural_fts'](s,params())
    assert 'fact_far' not in b.record_ids and 'fact_far' in c.record_ids
    assert c==STRATEGIES['structural_fts'](s,params()) and c.layers['fts']>0


def test_fts_empty_plan_adds_nothing():
    s=scene(rich_records(),plan='')
    assert STRATEGIES['structural_fts'](s,params()).record_ids==STRATEGIES['structural'](s,params()).record_ids


def test_full_a_saves_chars_on_long_timeline():
    timeline=[rec(f'h{i}','timeline','Подія номер '+str(i)+' '+'слово '*10,scene=i,kind='timeline') for i in range(1,100)]
    s=scene(timeline=timeline,number=100)
    full=STRATEGIES['full'](s,params());a=STRATEGIES['full_a'](s,params(timeline_window=20))
    assert a.chars<full.chars and a.layers['timeline']==20


def test_fts_never_adds_timeline_category_records():
    records=rich_records()+[rec('tl1','timeline','Маяк на скелі горів',kind=None)]
    sel=STRATEGIES['structural_fts'](scene(records,plan='маяк на скелі'),params())
    assert 'tl1' not in sel.record_ids


@pytest.mark.parametrize('measure',['conservative','realistic'])
def test_budget_respected_with_json_escaped_quotes(measure):
    quoted=[rec(f'q{i}','facts','Остап сказав "так" і "ні" \\ "може" '*3) for i in range(40)]
    s=scene(quoted,cast=('c2',))
    for n in (700,1500,3000):
        p=params(memory_budget_tokens=n,measure=measure)
        sel=STRATEGIES['structural'](s,p)
        assert sel.overflow or measured(sel,p)<=n
