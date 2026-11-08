import pytest

from memory_bench.strategies import STRATEGIES, Params
from memory_bench.synthetic import Rates, fit_linear, generate, measure_rates
from tests.retrieval_bench.helpers import rec, scene

R=Rates(active_per_scene={'facts':2.0,'character_states':1.5,'open_threads':0.5},timeline_per_scene=1.0,
        updates_per_scene={'character_states':0.6,'open_threads':0.2},
        text_len={'facts':80.0,'character_states':60.0,'open_threads':70.0,'timeline':50.0},
        cast_size=2.5,hero_share=0.8,first_meetings_per_scene=0.15,hero_state_share=0.4,other_state_share=0.4,
        mention_share=0.7)


def test_generate_is_deterministic():
    assert generate(R,50,seed=1)==generate(R,50,seed=1)
    assert generate(R,50,seed=1)!=generate(R,50,seed=2)


def test_generate_rates_roundtrip():
    got=measure_rates(generate(R,400))
    for key in ('facts','character_states','open_threads'):
        assert got.active_per_scene[key]==pytest.approx(R.active_per_scene[key],rel=0.1)
    assert got.timeline_per_scene==pytest.approx(R.timeline_per_scene,rel=0.1)
    assert got.cast_size==pytest.approx(R.cast_size,rel=0.15)
    assert got.hero_share==pytest.approx(R.hero_share,abs=0.08)
    assert got.updates_per_scene['character_states']==pytest.approx(R.updates_per_scene['character_states'],rel=0.2)
    assert got.text_len['facts']==pytest.approx(R.text_len['facts'],rel=0.15)
    assert got.mention_share==pytest.approx(R.mention_share,abs=0.1)


def test_generate_sample_every_keeps_last_scene():
    scenes=generate(R,100,sample_every=30)
    assert [s.number for s in scenes]==[1,31,61,91,100]


def test_measure_rates_from_handmade_scenes():
    last=scene([rec('f','facts','Марія тут'),rec('s','character_states','Марія сидить',['c1'])],
               timeline=[rec('h','timeline','Подія',kind='timeline')],number=2,cast=('c1','c2'),targets=('s',))
    first=scene([],number=1,cast=('c1',),id='s1')
    rates=measure_rates([first,last])
    assert rates.active_per_scene['facts']==0.5 and rates.timeline_per_scene==0.5
    assert rates.updates_per_scene['character_states']==0.5 and rates.cast_size==1.5 and rates.hero_share==1.0


def test_fit_linear_exact():
    assert fit_linear([(1,3.0),(2,5.0),(3,7.0)])==pytest.approx((2.0,1.0))
    with pytest.raises(ValueError):fit_linear([(1,1.0)])


def test_structural_stays_in_budget_on_long_synthetic_while_full_does_not():
    p=Params(memory_budget_tokens=20000,measure='conservative',core_mode='upper')
    scenes=generate(R,3000,sample_every=500)
    last=scenes[-1]
    assert STRATEGIES['full'](last,p).overflow
    for s in scenes:
        sel=STRATEGIES['structural_fts'](s,p)
        assert sel.overflow or sel.tokens_conservative<=20000
