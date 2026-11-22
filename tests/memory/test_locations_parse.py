"""MEMORY-LOCATIONS-S01: the «Локація:» line of a plan gives location paths; identity is the normalized full path."""
import pytest

from storygen.locations import (canonical, location_id, neighbourhood, normalize, parse_locations, prefixes,
    similar, Place)



@pytest.mark.req('MEMORY-LOCATIONS')
def test_commas_semicolons_arrows_and_sequence_words_separate_locations():
    assert parse_locations('Дім, двір; сад → озеро потім ліс далі поле згодом міст') == [
        ('Дім',),('двір',),('сад',),('озеро',),('ліс',),('поле',),('міст',)]
    assert parse_locations('House then yard later street') == [('House',),('yard',),('street',)]
    assert parse_locations('дім Потім двір') == [('дім',),('двір',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_and_words_stay_inside_a_name():
    assert parse_locations('Сад і город, двір та хлів') == [('Сад і город',),('двір та хлів',)]
    assert parse_locations('Bed and breakfast') == [('Bed and breakfast',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_sequence_word_inside_a_word_is_not_a_separator():
    assert parse_locations('Подалі від дому') == [('Подалі від дому',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_slash_nests_a_location():
    assert parse_locations('Квартира Джорджа / вітальня, двір') == [('Квартира Джорджа','вітальня'),('двір',)]
    assert parse_locations('Квартира Джорджа/вітальня') == [('Квартира Джорджа','вітальня')]
    assert prefixes(('А','Б','В')) == [('А',),('А','Б'),('А','Б','В')]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_empty_values_give_no_locations():
    assert parse_locations('') == []
    assert parse_locations(' , ; → потім ') == []
    assert parse_locations('Дім / , двір') == [('Дім',),('двір',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_repeats_by_key_are_dropped_in_order():
    assert parse_locations('Дім, двір, дім.') == [('Дім',),('двір',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_normalize_ignores_case_spaces_quotes_and_final_punctuation():
    assert normalize(('  «Маєток  Джорджа»', 'Вітальня.')) == 'маєток джорджа / вітальня'
    assert normalize(('Маєток Джорджа',)) != normalize(('Маєток Джорджа біля озера',))


@pytest.mark.req('MEMORY-LOCATIONS')
def test_id_is_deterministic_per_story_and_key():
    key=normalize(('Дім',))
    assert location_id('s1',key) == location_id('s1',key)
    assert location_id('s1',key) != location_id('s2',key)
    assert location_id('s1',key).startswith('loc_') and len(location_id('s1',key)) == 20


@pytest.mark.req('MEMORY-LOCATIONS')
@pytest.mark.parametrize('a,b,expected',[
    ('Маєток / вітальня','Квартира / вітальня',True),     # the same leaf
    ('Маєток Джорджа','Маєток Джорджа біля озера',True),  # the words of one inside the other
    ('Квартира Джорджа','Квартира Джоржа',True),          # a small edit distance
    ('Дім','Ліс',False),
    ('Квартира Джорджа','Офіс Марти',False),
])
def test_similar(a,b,expected):
    assert similar(a,b) is expected


@pytest.mark.req('MEMORY-LOCATIONS')
def test_canonical_follows_merges_and_stops_on_a_cycle():
    assert canonical({'a':'b','b':'c','c':None},'a') == 'c'
    assert canonical({'a':'b','b':'a'},'a') in {'a','b'}
    assert canonical({},'x') == 'x'


@pytest.mark.req('MEMORY-LOCATIONS')
def test_neighbourhood_has_ancestors_descendants_and_merged_ids():
    places={'h':Place('h',None,None),'k':Place('k','h',None),'t':Place('t','k',None),'o':Place('o',None,None),
            'm':Place('m',None,'k'),'y':Place('y',None,None)}
    assert neighbourhood(places,['k']) == sorted(['h','k','t','m'])
    assert neighbourhood(places,['m']) == sorted(['h','k','t','m'])
    assert neighbourhood(places,[]) == []
