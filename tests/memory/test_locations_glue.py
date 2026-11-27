"""MEMORY-LOCATIONS-S09: glued phrases of a story are not cut by the «Локація:» parse; glue_cuts give the phrase across each cut."""
import unicodedata

import pytest

from storygen.locations import glue_cuts, glue_key, parse_locations

P = ['бар, в якому пахне кавою']


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glued_phrase_is_not_cut():
    assert parse_locations('Бар, в якому пахне кавою, вулиця', P) == [('Бар, в якому пахне кавою',), ('вулиця',)]
    assert parse_locations('Місто / бар,  в якому пахне   кавою / тераса та двір', P) == [
        ('Місто', 'бар, в якому пахне кавою', 'тераса'), ('двір',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_keeps_its_separator_and_word_bounds():
    assert parse_locations('бар та в якому пахне кавою', P) == [('бар',), ('в якому пахне кавою',)]
    assert parse_locations('Ґрунтобар, в якому пахне кавою', P) == [('Ґрунтобар',), ('в якому пахне кавою',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_matches_case_nfd_apostrophes_and_punctuation_spacing():
    assert parse_locations(unicodedata.normalize('NFD', 'Бар, в якому пахне кавою, двір'), P) == [
        ('Бар, в якому пахне кавою',), ('двір',)]
    assert parse_locations("Комора з п'ятьма полицями, двір", ['комора з п’ятьма полицями, двір']) == [
        ("Комора з п'ятьма полицями, двір",)]
    assert parse_locations('бар,в якому пахне кавою', P) == [('бар,в якому пахне кавою',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_overlapping_and_chained_glues():
    line = 'бар, в якому пахне кавою, де грає джаз, вулиця'
    assert parse_locations(line, P + ['кавою, де грає джаз']) == [('бар, в якому пахне кавою, де грає джаз',), ('вулиця',)]
    assert parse_locations(line, P + ['бар, в якому пахне кавою, де грає джаз']) == [
        ('бар, в якому пахне кавою, де грає джаз',), ('вулиця',)]


@pytest.mark.req('MEMORY-LOCATIONS')
def test_without_glues_the_parse_is_unchanged():
    for line in ['Дім, двір; сад → озеро потім ліс', 'Бар «Ніч та день» та вулиця', 'Хата (кухня, сіни та комора) та двір']:
        assert parse_locations(line, ()) == parse_locations(line)


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_key():
    assert glue_key('  Бар ,  в якому  П’ЯТЬ ') == glue_key("бар, в якому п'ять") == "бар, в якому п'ять"


@pytest.mark.req('MEMORY-LOCATIONS')
def test_glue_cuts_give_the_phrase_across_each_cut():
    assert glue_cuts('Місто / бар, в якому пахне кавою / тераса та двір') == [
        ('бар, в якому пахне кавою', ('Місто', 'бар'), ('в якому пахне кавою', 'тераса')),
        ('тераса та двір', ('в якому пахне кавою', 'тераса'), ('двір',))]
    assert glue_cuts('Кафе «бар, в якому», двір')[0][0] == 'Кафе «бар, в якому»'
    assert glue_cuts('Бар, в якому пахне кавою, вулиця', P) == [
        ('Бар, в якому пахне кавою, вулиця', ('Бар, в якому пахне кавою',), ('вулиця',))]
    assert glue_cuts('Дім / , двір') == []
