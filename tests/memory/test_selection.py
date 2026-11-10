import pytest

from storygen.memory.projection import MemoryItem, render_memory
from storygen.memory.selection import (ATMOSPHERE_SHARE, LAYERS, CoreOverflow, SelectionInput, classify, fts_rank,
    minimal_chars, select_memory, timeline_note)

NAMES={'h':'Ганна','a':'Оля','x':'Петро'}


def item(claim,section,text,*,chars=(),scene=1,slot=None,owner=None):
    line=f'{slot}: {text}' if section=='core' else ('— '+(f'Сцена {scene}: ' if section=='timeline' and scene is not None else '')+text)
    return MemoryItem(claim,section,owner,line,text,tuple(chars),slot,scene)


def scene_items():
    return (item('loc','core','Квартира на Подолі',chars=['h'],slot='місце',owner='h'),
        item('mood_now','character_states','Ганна втомлена',chars=['h'],scene=29),
        item('mood_old','character_states','Ганна боїться води',chars=['h'],scene=2),
        item('ola','character_states','Оля сердиться',chars=['a'],scene=4),
        item('rain','character_states','Іде дощ',scene=5),
        item('pair','character_states','Петро чекає листа',chars=['x'],scene=5),
        item('t_ola','open_threads','Оля винна гроші',scene=3),
        item('t_far','open_threads','Скарб у горах',scene=3),
        item('f_ola','facts','Оля живе на Подолі',scene=1),
        item('f_hero','facts','Ганна народилася в Одесі',scene=1),
        item('f_none','facts','Маяк збудовано 1890 року',scene=1),
        item('tl_old','timeline','Ганна приїхала',scene=1),
        item('tl_new','timeline','Ганна знайшла лист',scene=28))


def inp(items=None,*,query='',kinds=None,scene_day=None,day_keys=None,number=30):
    return SelectionInput(tuple(items or scene_items()),'s11',number,('h','a'),('h',),NAMES,query,kinds or {},scene_day,day_keys or {})


def layer_of(layers):
    return {i.claim_id:name for name,items in layers.items() for i in items}


def test_every_candidate_in_exactly_one_layer():
    layers=classify(inp())
    ids=[i.claim_id for items in layers.values() for i in items]
    assert sorted(ids)==sorted(i.claim_id for i in scene_items()) and len(ids)==len(set(ids))
    assert layer_of(layers)=={'loc':'core','mood_now':'hero_recent','mood_old':'atmosphere','ola':'present','rain':'general',
        'pair':'fts','t_ola':'threads','t_far':'fts','f_ola':'facts','f_hero':'atmosphere','f_none':'fts',
        'tl_old':'timeline','tl_new':'timeline'}


def test_hero_recent_by_story_day_then_by_three_scenes():
    # Same story day: an old state changed on this day is recent; another day is atmosphere.
    by_day=layer_of(classify(inp(scene_day='day:3',day_keys={2:'day:3',29:'day:2'})))
    assert by_day['mood_old']=='hero_recent' and by_day['mood_now']=='atmosphere'
    # Without a day key on either side: changed within the last three scenes.
    fallback=layer_of(classify(inp(scene_day='day:3',day_keys={29:None})))
    assert fallback['mood_now']=='hero_recent'


def test_author_overrides_win_but_slots_stay_core():
    layers=layer_of(classify(inp(kinds={'f_none':'core','ola':'atmosphere','loc':'atmosphere'})))
    assert layers['f_none']=='core' and layers['ola']=='atmosphere' and layers['loc']=='core'


def test_full_budget_selects_everything_but_old_timeline():
    full=render_memory(list(scene_items()),['h'],NAMES)
    result=select_memory(inp(query='скарб маяк петро'),len(full)+500)
    assert set(result.selected_claim_ids)=={i.claim_id for i in scene_items()}-{'tl_old'}
    assert result.dropped['timeline']==1 and result.timeline_note=='Не показано записів: 1 (сцени 1).'
    assert result.text.index('ХРОНОЛОГІЯ\n— Не показано записів: 1 (сцени 1).\n— Сцена 28: Ганна знайшла лист')>0


def test_budget_is_respected_and_every_line_counted():
    candidates=len(scene_items())
    for budget in range(minimal_chars(inp()),700,7):
        result=select_memory(inp(query='скарб маяк петро'),budget)
        assert len(result.text)<=budget
        assert sum(result.layers.values())+sum(result.dropped.values())==candidates
        assert sum(result.layers.values())==len(result.selected_claim_ids)
        assert 'Квартира на Подолі' in result.text


def test_priority_order_drops_lower_layers_first():
    base=minimal_chars(inp())
    result=select_memory(inp(),base+len('— Ганна втомлена')+1)
    assert result.selected_claim_ids==('loc','mood_now')
    assert result.dropped['threads']==1 and result.dropped['facts']==1


def test_core_overflow_never_cuts_the_core():
    with pytest.raises(CoreOverflow) as error:
        select_memory(inp(),minimal_chars(inp())-1)
    assert error.value.needed==minimal_chars(inp())


def test_atmosphere_quota_and_hash_order():
    many=[item('loc','core','Квартира',chars=['h'],slot='місце',owner='h')]+[
        item(f'old{n}','character_states',f'Давній стан Ганни номер {n}',chars=['h'],scene=1) for n in range(30)]
    budget=2000
    result=select_memory(inp(many),budget)
    used=sum(len(i.line)+1 for i in many if i.claim_id in result.selected_claim_ids and i.section!='core')
    assert 0<result.layers['atmosphere'] and used<=int(ATMOSPHERE_SHARE*budget)
    order=[i.claim_id for i in classify(inp(many))['atmosphere']]
    assert order!=sorted(order) and order==[i.claim_id for i in classify(inp(many))['atmosphere']]
    other=SelectionInput(tuple(many),'s12',11,('h','a'),('h',),NAMES)
    assert [i.claim_id for i in classify(other)['atmosphere']]!=order


def test_fts_ranks_by_query_ties_by_claim_and_empty_query_ranks_nothing():
    pool=[item('b','facts','маяк на скелі'),item('a','facts','маяк на скелі'),item('c','facts','сад')]
    assert [i.claim_id for i in fts_rank(pool,'маяк')]==['a','b']
    assert fts_rank(pool,'')==[] and fts_rank(pool,'ок')==[]
    result=select_memory(inp(query=''),5000)
    assert result.layers['fts']==0 and result.dropped['fts']==3


def test_timeline_note_compresses_scene_ranges():
    dropped=[item(f't{n}','timeline','x',scene=n) for n in (1,2,3,5,7,8)]+[item('tn','timeline','x',scene=None)]
    assert timeline_note(dropped)=='Не показано записів: 7 (сцени 1–3, 5, 7–8).'
    assert timeline_note([])is None


def test_recent_timeline_dropped_by_budget_is_noted():
    result=select_memory(inp(),minimal_chars(inp()))
    assert result.selected_claim_ids==('loc',)
    assert result.timeline_note=='Не показано записів: 2 (сцени 1, 28).'


def test_selection_is_deterministic():
    first=select_memory(inp(query='маяк'),400)
    assert all(select_memory(inp(query='маяк'),400)==first for _ in range(3))
    assert set(first.layers)==set(LAYERS)==set(first.dropped)
