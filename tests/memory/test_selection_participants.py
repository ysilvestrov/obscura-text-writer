"""MEMORY-ENTITIES-S02, S03: memory selection by record participants and the `past` layer of old timeline."""
import dataclasses

import pytest

from storygen.generation.context import SELECTED_PROJECTION, SUMMARY_PROJECTION
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.memory.projection import memory_items
from storygen.memory.selection import LAYERS, classify, minimal_chars, narrow_catalog, select_memory
from storygen.memory.summaries import SummaryCandidate
from tests.memory.test_selection import inp, item, layer_of, scene_items


def who(entry, *ids):
    return dataclasses.replace(entry, participant_ids=tuple(ids))


def old(claim, scene, *ids, text='Оля прийшла до старого маяка й довго говорила з доглядачем про шторм'):
    return who(item(claim, 'timeline', f'{text} {scene}', scene=scene), *ids)


@pytest.mark.req('MEMORY-ENTITIES')
def test_thread_with_a_participant_of_the_scene_goes_to_threads_even_with_an_inflected_name():
    thread = item('t', 'open_threads', 'Олі винні гроші', scene=3)
    assert layer_of(classify(inp((thread,))))['t'] == 'fts'
    assert layer_of(classify(inp((who(thread, 'a'),))))['t'] == 'threads'


@pytest.mark.req('MEMORY-ENTITIES')
def test_thread_with_participants_outside_the_scene_does_not_fall_back_to_names():
    thread = item('t', 'open_threads', 'Оля винна гроші', scene=3)
    assert layer_of(classify(inp((thread,))))['t'] == 'threads'
    assert layer_of(classify(inp((who(thread, 'x'),))))['t'] == 'fts'


@pytest.mark.req('MEMORY-ENTITIES')
def test_record_without_participants_is_classified_by_names_as_before():
    assert layer_of(classify(inp())) == {'loc': 'core', 'mood_now': 'hero_recent', 'mood_old': 'atmosphere', 'ola': 'present',
        'rain': 'general', 'pair': 'fts', 't_ola': 'threads', 't_far': 'fts', 'f_ola': 'facts', 'f_hero': 'atmosphere',
        'f_none': 'fts', 'tl_old': 'timeline', 'tl_new': 'timeline'}
    # Old timeline without participants and locations stays in `timeline`, as before.
    late = layer_of(classify(inp(number=60)))
    assert late['tl_old'] == late['tl_new'] == 'timeline' and 'past' not in late.values()


@pytest.mark.req('MEMORY-ENTITIES')
def test_fact_only_about_the_hero_goes_to_atmosphere_by_ids():
    fact = item('f', 'facts', 'Народилася в Одесі', scene=1)
    assert layer_of(classify(inp((fact,))))['f'] == 'fts'
    assert layer_of(classify(inp((who(fact, 'h'),))))['f'] == 'atmosphere'
    assert layer_of(classify(inp((who(fact, 'h', 'a'),))))['f'] == 'facts'
    # Participants decide over names: the text names Оля, but the fact is only about the hero.
    assert layer_of(classify(inp((who(item('g', 'facts', 'Ганна позичила Олі книжку', scene=1), 'h'),))))['g'] == 'atmosphere'


@pytest.mark.req('MEMORY-ENTITIES')
def test_old_timeline_with_a_non_hero_participant_goes_to_past():
    layers = layer_of(classify(inp((old('a2', 2, 'a'), old('h2', 2, 'h'), old('a30', 30, 'a'), old('x2', 2, 'x')), number=40)))
    assert layers == {'a2': 'past', 'h2': 'timeline', 'a30': 'timeline', 'x2': 'timeline'}
    assert LAYERS.index('past') == LAYERS.index('place') + 1


@pytest.mark.req('MEMORY-ENTITIES')
def test_old_timeline_in_the_neighbourhood_goes_to_past():
    here = dataclasses.replace(old('k', 2), location_ids=('loc_kitchen',))
    away = dataclasses.replace(old('f', 2), location_ids=('loc_forest',))
    selection = dataclasses.replace(inp((here, away), number=40), place=frozenset({'loc_kitchen'}))
    assert layer_of(classify(selection)) == {'k': 'past', 'f': 'timeline'}


def _one_past_budget(selection):
    for budget in range(minimal_chars(selection), 2000):
        result = select_memory(selection, budget)
        if result.layers['past'] == 1:return result
    raise AssertionError('no budget for one past entry')


@pytest.mark.req('MEMORY-ENTITIES')
def test_past_is_taken_newest_first_and_not_when_its_block_summary_is_taken():
    entries = (old('p3', 3, 'a'), old('p8', 8, 'a'))
    result = _one_past_budget(inp(entries, number=40))
    assert 'p8' in result.selected_claim_ids and 'p3' not in result.selected_claim_ids
    assert result.dropped['past'] == 1 and result.timeline_note == 'Не показано записів: 1 (сцени 3).'
    summary = SummaryCandidate('range:1-10', 'v1', 1, 10, '— Підсумок сцен 1–10: Оля приходила.')
    covered = select_memory(dataclasses.replace(inp(entries, number=40), summaries=(summary,)), 5000)
    assert covered.summaries == (('range:1-10', 'v1'),) and not {'p3', 'p8'} & set(covered.selected_claim_ids)
    assert covered.layers['past'] == covered.dropped['past'] == 0 and covered.timeline_note is None


@pytest.mark.req('MEMORY-ENTITIES')
def test_timeline_note_counts_untaken_past_and_skips_taken():
    result = _one_past_budget(inp((old('p3', 3, 'a'), old('p8', 8, 'a'), old('t5', 5)), number=40))
    assert 'p8' in result.selected_claim_ids and result.timeline_note == 'Не показано записів: 2 (сцени 3, 5).'
    assert 'Сцена 8:' in result.text
    # The smallest section counts every old timeline entry, past included.
    smallest = inp((old('p3', 3, 'a'), old('p8', 8, 'a'), old('t5', 5)), number=40)
    assert 'Не показано записів: 3 (сцени 3, 5, 8).' in select_memory(smallest, minimal_chars(smallest)).text


@pytest.mark.req('MEMORY-ENTITIES')
def test_hero_in_every_scene_does_not_fill_past():
    entries = tuple(old(f'h{n}', n, 'h', text='Ганна працює') for n in range(1, 31))
    selection = inp(entries, number=60)
    assert classify(selection)['past'] == []
    result = select_memory(selection, 5000)
    assert result.layers['past'] == result.dropped['past'] == 0 and result.dropped['timeline'] == 30


@pytest.mark.req('MEMORY-ENTITIES')
def test_narrow_catalog_keeps_facts_by_participants_and_names_without_them():
    events = [_add_event('facts', 'Хтось приніс листа', 'p1', 'q', 0, participant_ids=['a']),
              _add_event('facts', 'Оля живе на Подолі', 'p1', 'q', 1),
              _add_event('facts', 'Оля сміється з Петра', 'p1', 'q', 2, participant_ids=['x']),
              _add_event('facts', 'Петро живе в лісі', 'p1', 'q', 3)]
    journal = MemoryJournal(schema_version=4, source_prose_ids=['p1'], events=events)
    keep = narrow_catalog(journal, ['h', 'a'], ['h'], {'h': 'Ганна', 'a': 'Оля', 'x': 'Петро'}, '', 2, {'p1': 1}).keep
    assert {events[0].claim_id, events[1].claim_id} <= keep and not {events[2].claim_id, events[3].claim_id} & keep


@pytest.mark.req('MEMORY-ENTITIES')
def test_memory_items_carry_participants():
    events = [_add_event('timeline', 'Оля прийшла', 'p1', 'q', 0, participant_ids=['a']), _add_event('facts', 'Маяк', 'p1', 'q', 1)]
    items, _ = memory_items(MemoryJournal(schema_version=4, source_prose_ids=['p1'], events=events), ['h'], {'p1': 1})
    assert {i.text: i.participant_ids for i in items} == {'Оля прийшла': ('a',), 'Маяк': ()}


@pytest.mark.req('MEMORY-ENTITIES')
def test_selected_projection_version_is_v4():
    assert SELECTED_PROJECTION == 'memory-uk-v4-selected' and SUMMARY_PROJECTION == 'memory-uk-v4-selected-summary'


@pytest.mark.req('MEMORY-ENTITIES')
def test_stale_summary_warns_about_an_untaken_past_entry_only():
    from storygen.memory.summaries import StaleSummary
    selection = dataclasses.replace(inp((old('p3', 3, 'a'), old('p8', 8, 'a')), number=40),
        stale_summaries=(StaleSummary('range:1-10', 1, 10, 'stale'),))
    assert select_memory(selection, minimal_chars(selection)).warnings == ('Підсумок сцен 1–10 застарів: перебудуйте його в панелі пам’яті.',)
    assert select_memory(selection, 5000).warnings == ()


@pytest.mark.req('MEMORY-ENTITIES')
def test_every_past_entry_is_taken_covered_or_counted_under_any_budget():
    entries = (old('p3', 3, 'a'), old('p8', 8, 'a')) + tuple(item(f't{n}', 'timeline', f'Подія номер {n} у місті', scene=n) for n in range(25, 40))
    summary = SummaryCandidate('range:1-10', 'v1', 1, 10, '— Підсумок сцен 1–10: ' + 'довгий опис ' * 20)
    selection = dataclasses.replace(inp(entries, number=40), summaries=(summary,))
    popped = 0
    for budget in range(minimal_chars(selection), 2500, 5):
        result = select_memory(selection, budget)
        covered = 2 if result.summaries else 0
        assert len(result.text) <= budget
        # `- 1`: the one summary candidate is counted in layers or dropped 'summary' but is not an entry.
        assert sum(result.layers.values()) + sum(result.dropped.values()) - 1 + covered == len(entries)
        if not result.summaries:
            # MEMORY-SELECT І6: a summary that did not fit or was trimmed returns each entry of its block to its own layer.
            assert result.layers['past'] + result.dropped['past'] == 2 and result.layers['timeline'] + result.dropped['timeline'] == 15
            popped += result.dropped['summary'] == 1 and result.layers['past'] == 0
    assert popped  # the sweep reaches budgets where the summary is trimmed and its past entries are not taken
