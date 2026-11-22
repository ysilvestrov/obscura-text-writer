"""MEMORY-LOCATIONS-S05: the `place` layer of memory selection, the projection and the narrowed catalog."""
import dataclasses

import pytest

from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.projection import MemoryItem, memory_items
from storygen.memory.selection import LAYERS, classify, narrow_catalog, select_memory
from tests.memory.test_selection import inp, item, layer_of

pytestmark = pytest.mark.req('MEMORY-LOCATIONS')

HERE = frozenset({'loc_house', 'loc_kitchen', 'loc_old'})  # the scene's neighbourhood: kitchen, its house, a merged id


def at(entry, *ids):
    return dataclasses.replace(entry, location_ids=tuple(ids))


def placed():
    return (item('core', 'core', 'Квартира', chars=['h'], slot='місце', owner='h'),
            at(item('hero', 'character_states', 'Ганна втомлена', chars=['h'], scene=29), 'loc_kitchen'),
            at(item('hero_old', 'character_states', 'Ганна боїться води', chars=['h'], scene=2), 'loc_kitchen'),
            at(item('ola', 'character_states', 'Оля сердиться', chars=['a'], scene=4), 'loc_kitchen'),
            at(item('door', 'character_states', 'Двері зачинені', scene=5), 'loc_house'),
            at(item('petro', 'character_states', 'Петро чекає листа', chars=['x'], scene=5), 'loc_old'),
            at(item('far', 'character_states', 'Петро в лісі', chars=['x'], scene=5), 'loc_forest'),
            at(item('t_far', 'open_threads', 'Скарб під підлогою', scene=3), 'loc_house'),
            at(item('t_ola', 'open_threads', 'Оля винна гроші', scene=3), 'loc_house'),
            at(item('f_room', 'facts', 'Маяк видно з вікна', scene=1), 'loc_kitchen'),
            at(item('tl', 'timeline', 'Ганна прийшла', scene=28), 'loc_kitchen'))


def test_place_layer_follows_present():
    assert LAYERS.index('place') == LAYERS.index('present') + 1


def test_records_of_the_neighbourhood_go_to_place_and_higher_layers_keep_theirs():
    layers = layer_of(classify(dataclasses.replace(inp(placed()), place=HERE)))
    assert layers == {'core': 'core', 'hero': 'hero_recent', 'hero_old': 'place', 'ola': 'present', 'door': 'place',
                      'petro': 'place', 'far': 'fts', 't_far': 'place', 't_ola': 'threads', 'f_room': 'place', 'tl': 'timeline'}


def test_without_a_neighbourhood_nothing_changes():
    plain = layer_of(classify(inp(placed())))
    assert 'place' not in plain.values()
    assert plain == layer_of(classify(inp(tuple(dataclasses.replace(i, location_ids=()) for i in placed()))))


def test_place_is_taken_before_general_and_facts():
    selection = dataclasses.replace(inp(placed()), place=HERE)
    result = select_memory(selection, 10_000)
    assert result.layers['place'] == 5 and {'hero_old', 'door', 'petro', 't_far', 'f_room'} <= set(result.selected_claim_ids)


def test_projection_keeps_a_state_of_an_absent_character_in_the_neighbourhood():
    events = [_add_event('character_states', 'Петро чекає листа', 'p1', 'q', 0, ['x'], location_ids=['loc_old']),
              _add_event('character_states', 'Петро в лісі', 'p1', 'q', 1, ['x'], location_ids=['loc_forest'])]
    journal = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=events)
    items, metrics = memory_items(journal, ['h'], {'p1': 1}, place=HERE)
    assert [i.text for i in items] == ['Петро чекає листа'] and items[0].location_ids == ('loc_old',)
    assert metrics['omitted_state_count'] == 1
    assert memory_items(journal, ['h'], {'p1': 1})[0] == []


def test_narrow_catalog_keeps_states_and_facts_of_the_neighbourhood():
    events = [_add_event('character_states', f'Петро тримає річ {n}', 'p1', 'q', n, ['x']) for n in range(30)]
    events += [_add_event('character_states', 'Петро чекає листа', 'p1', 'q', 0, ['x'], location_ids=['loc_old']),
               _add_event('facts', 'Маяк видно з вікна', 'p1', 'q', 0, location_ids=['loc_kitchen'])]
    journal = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=events)
    keep = narrow_catalog(journal, ['h'], ['h'], {'h': 'Ганна'}, 'кухня', 2, {'p1': 1}, place=HERE).keep
    assert {events[-2].claim_id, events[-1].claim_id} <= keep
    assert not {events[-2].claim_id, events[-1].claim_id} & narrow_catalog(journal, ['h'], ['h'], {'h': 'Ганна'}, 'кухня', 2, {'p1': 1}).keep
