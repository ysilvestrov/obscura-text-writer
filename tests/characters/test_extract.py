"""CHARACTER-EXTRACT (R-51): the pure logic of character extraction from prose; no IO, no model."""
import json
from pathlib import Path

import pytest

from storygen.characters.extract import (
    ExtractState, CatalogueCard, SceneMeta, SceneProse, apply_group, catalogue_text, find_quote, finalize,
    normalize_with_map, parse_extract, plan_groups, short_ids, SKIP_INPUT_LIMIT)

DATA = Path(__file__).parent.parent / 'fixtures' / 'character_extract'
P1 = ('Іванка йшла лісом і насвистувала.\n\nАнничка сміялася: «Ходімо додому — вже пізно, мамо!» Стара мовчки\n'
      'дивилася на дорогу. **Тут була її хата.**')
P2 = 'Наступного ранку Іванка прокинулась першою. Мирон приніс воду з колодязя. Ганнуся подякувала.'
GROUP = [SceneProse('sc1', 'v1', P1), SceneProse('sc2', 'v2', P2)]
ANNA = CatalogueCard(ref='card-1', name='Анна', names=['Анна', 'Анничка'], existing=True)


def fixture(name):
    return parse_extract((DATA / f'extract_{name}.json').read_text(encoding='utf-8'))


def state(*cards):
    return ExtractState(catalogue=list(cards), scene_order=['sc1', 'sc2'])


def run(st, response):
    if isinstance(response, str):
        response = fixture(response)
    card_numbers, scene_numbers = short_ids(st, ['sc1', 'sc2'])
    return apply_group(st, response, GROUP, scene_numbers=scene_numbers, card_numbers=card_numbers)


def new_cards(st):
    return [card for card in st.catalogue if not card.existing]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_normalized_quote_maps_to_original_span():
    text = 'Дар’я сказала:\n«Ходімо — це **добре** місце»,  і пішла.'
    hit = find_quote([SceneProse('s', 'v', text)], 'ходімо - це добре місце')
    assert hit.quote == 'Ходімо — це **добре** місце' and hit.quote in text
    assert (hit.scene_id, hit.version_id) == ('s', 'v')
    assert find_quote([SceneProse('s', 'v', text)], "ДАР'Я сказала: «Ходімо").quote == 'Дар’я сказала:\n«Ходімо'
    normalized, mapping = normalize_with_map(text)
    assert len(mapping) == len(normalized) and text[mapping[0]] == 'Д'
    assert normalized.startswith("дар'я сказала: \"ходімо - це добре")


@pytest.mark.req('CHARACTER-EXTRACT')
def test_quote_across_scenes_rejected():
    scenes = [SceneProse('a', 'va', 'Кінець першої сцени.'), SceneProse('b', 'vb', 'Початок другої сцени.')]
    assert find_quote(scenes, 'Кінець першої сцени. Початок другої') is None
    assert find_quote(scenes, 'Початок другої').scene_id == 'b'
    assert find_quote(scenes, '...') is None


@pytest.mark.req('CHARACTER-EXTRACT')
def test_groups_whole_scenes_to_budget():
    scenes = [('a', 400, 1), ('b', 400, 1), ('c', 400, 1), ('d', 100, 1)]
    assert plan_groups(scenes, 1000, lambda ids: True) == ([['a', 'b'], ['c', 'd']], [])


@pytest.mark.req('CHARACTER-EXTRACT')
def test_oversized_scene_own_group():
    scenes = [('a', 100, 1), ('b', 3000, 1), ('c', 100, 1)]
    assert plan_groups(scenes, 1000, lambda ids: True) == ([['a'], ['b'], ['c']], [])


@pytest.mark.req('CHARACTER-EXTRACT')
def test_unfit_group_splits_then_skips():
    scenes = [('a', 10, 1), ('b', 10, 1), ('c', 10, 1), ('d', 10, 1)]
    seen = []

    def fits(ids):
        seen.append(list(ids))
        return len(ids) <= 2 and 'd' not in ids
    groups, skipped = plan_groups(scenes, 1000, fits)
    assert groups == [['a', 'b'], ['c']] and skipped == [('d', SKIP_INPUT_LIMIT)]
    assert seen[0] == ['a', 'b', 'c', 'd']
    assert SKIP_INPUT_LIMIT == "не вміщується в ліміт входу ролі «Пам'ять»"


@pytest.mark.req('CHARACTER-EXTRACT')
def test_card_without_verbatim_quote_dropped():
    assert new_cards(run(state(), 'foreign_quote')) == []
    response = parse_extract(json.dumps({'new_cards': [{'key': 'n1', 'name': 'Мирон', 'quotes': ['Мирон ніс воду']}]}))
    assert new_cards(run(state(), response)) == []


@pytest.mark.req('CHARACTER-EXTRACT')
def test_alias_absent_from_prose_dropped():
    result = run(state(), 'valid')
    assert [card.name for card in new_cards(result)] == ['Іванка', 'Анничка', 'Мирон']
    assert new_cards(result)[0].names == ['Іванка'] and new_cards(result)[0].added_names == []
    card_updates = parse_extract(json.dumps({'card_updates': [{'id': 'c1', 'other_names': ['Мирон', 'Леся']}]}))
    updated = run(state(ANNA), card_updates)
    assert [(item.name, item.suggested) for item in updated.catalogue[0].added_names] == [('Мирон', True)]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_lowercase_alias_unsuggested():
    card = new_cards(run(state(), 'stara'))[0]
    assert [(item.name, item.suggested) for item in card.added_names] == [('стара', False)]
    assert card.quotes[0].quote == 'Стара мовчки\nдивилася на дорогу' and card.first_scene_id == 'sc1'
    assert card.quotes[0].version_id == 'v1'


@pytest.mark.req('CHARACTER-EXTRACT')
def test_duplicate_by_name_merges_as_names():
    result = run(state(ANNA), 'duplicate')
    assert new_cards(result) == [] and len(result.catalogue) == 1
    assert [(item.name, item.suggested) for item in result.catalogue[0].added_names] == [('Ганнуся', True)]
    assert result.catalogue[0].quotes == [] and result.casts == {'sc1': ['card-1']}
    twice = parse_extract(json.dumps({'new_cards': [
        {'key': 'n1', 'name': 'Мирон', 'quotes': ['Мирон приніс воду']},
        {'key': 'n2', 'name': 'мирон', 'other_names': ['Ганнуся'], 'quotes': ['Мирон приніс воду']}],
        'scenes': [{'scene': 's2', 'participants': ['n1', 'n2']}]}))
    merged = run(state(), twice)
    assert [card.name for card in merged.catalogue] == ['Мирон'] and merged.casts == {'sc2': ['new1']}
    assert [item.name for item in merged.catalogue[0].added_names] == ['Ганнуся']
    assert len(merged.catalogue[0].quotes) == 1


@pytest.mark.req('CHARACTER-EXTRACT')
def test_invented_scene_id_dropped():
    result = run(state(ANNA), 'invented_scene')
    assert result.casts == {'sc1': ['card-1']} and result.scores == {}
    assert result.catalogue[0].added_names == [] and result.groups_done == 1


@pytest.mark.req('CHARACTER-EXTRACT')
def test_empty_object_is_noop():
    st = state(ANNA)
    result = run(st, 'empty')
    assert result.catalogue == st.catalogue and result.casts == {} and result.scores == {}
    assert result.groups_done == 1 and st.groups_done == 0
    known_id_as_key = parse_extract(json.dumps({'new_cards': [
        {'key': 'c1', 'name': 'Мирон', 'quotes': ['Мирон приніс воду']}], 'scenes': [{'scene': 's2', 'participants': ['c1']}]}))
    assert run(st, known_id_as_key).catalogue == st.catalogue


@pytest.mark.req('CHARACTER-EXTRACT')
def test_valid_response_builds_cards_cast_and_scores():
    result = run(state(), 'valid')
    assert [card.ref for card in result.catalogue] == ['new1', 'new2', 'new3']
    assert result.casts == {'sc1': ['new1', 'new2'], 'sc2': ['new1', 'new3']}
    assert result.scores == {'new1': 0.7, 'new2': 0.2}
    assert result.catalogue[1].quotes[0].quote == 'Ходімо додому — вже пізно, мамо'
    assert catalogue_text(result).splitlines()[0] == 'c1: Іванка'
    assert catalogue_text(state(ANNA)) == 'c1: Анна (інші імена: Анничка)'
    assert short_ids(result, ['sc2']) == ({'c1': 'new1', 'c2': 'new2', 'c3': 'new3'}, {'s2': 'sc2'})


@pytest.mark.req('CHARACTER-EXTRACT')
@pytest.mark.parametrize('payload', [
    '', 'not json', '[]', '{"new_cards": [{"key": "n1", "name": "x", "quotes": [5]}]}',
    '{"new_cards": [{"key": "n1", "name": "x", "other_names": ["a"] , "quotes": ["a"]}], "new_cards": []}',
    '{"protagonist_candidates": [{"id": "c1", "score": NaN}]}',
])
def test_parse_rejects_invalid(payload):
    with pytest.raises(ValueError):
        parse_extract(payload)


@pytest.mark.req('CHARACTER-EXTRACT')
def test_parse_accepts_fence_and_ignores_extra():
    parsed = parse_extract('```json\n{"new_cards": [], "extra": 1}\n```')
    assert parsed.new_cards == [] and parsed.scenes == []


def cards4():
    return [CatalogueCard(ref=ref, name=ref.upper(), names=[ref.upper()], existing=ref == 'a') for ref in 'abcd']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_protagonist_threshold_and_author_marker():
    low = ExtractState(catalogue=cards4(), scores={'a': 0.6, 'b': 0.3, 'c': 0.2, 'd': 0.1})
    assert finalize(low, {}, False)['protagonist'] is None
    high = ExtractState(catalogue=cards4(), scores={'a': 0.5, 'b': 1.0, 'c': 0.5, 'd': 0.25})
    protagonist = finalize(high, {}, False)['protagonist']
    assert protagonist['ref'] == 'b'
    assert [item['ref'] for item in protagonist['scores']] == ['b', 'a', 'c']
    assert finalize(high, {}, True)['protagonist'] is None


@pytest.mark.req('CHARACTER-EXTRACT')
def test_cast_set_vs_add_and_ineligible():
    st = ExtractState(catalogue=[ANNA, CatalogueCard(ref='new1', name='Іванка', names=['Іванка'], existing=False)],
                      casts={'sc1': ['card-1', 'new1'], 'sc2': ['card-1'], 'sc3': ['new1'], 'sc4': ['card-1', 'new1'], 'sc5': []})
    metas = {'sc1': SceneMeta('sc1', True, []), 'sc2': SceneMeta('sc2', True, ['card-1']),
             'sc3': SceneMeta('sc3', False, []), 'sc4': SceneMeta('sc4', True, ['card-1']), 'sc5': SceneMeta('sc5', True, [])}
    result = finalize(st, metas, False)
    assert result['casts'] == [{'scene_id': 'sc1', 'mode': 'set', 'participants': ['card-1', 'new1']},
                               {'scene_id': 'sc4', 'mode': 'add', 'participants': ['new1']}]
    assert [card['key'] for card in result['cards']] == ['new1'] and 'fingerprint' not in result and 'source' not in result


@pytest.mark.req('CHARACTER-EXTRACT')
def test_finalize_cards_name_updates_and_skipped():
    result = run(run(state(ANNA), 'duplicate'), 'valid')
    final = finalize(result, {}, False)
    assert [card['name'] for card in final['cards']] == ['Іванка', 'Мирон']  # Анничка is a known name of card-1
    assert final['cards'][0]['first_scene_id'] == 'sc1' and final['cards'][0]['quotes'][0]['version_id'] == 'v1'
    assert final['name_updates'] == [{'card_id': 'card-1', 'names': [{'name': 'Ганнуся', 'suggested': True}]}]
    skipped = ExtractState(skipped=[('sc9', 'модель не дала відповіді')])
    assert finalize(skipped, {}, False)['skipped_scenes'] == [{'scene_id': 'sc9', 'reason': 'модель не дала відповіді'}]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_over_limit_values_are_trimmed_not_rejected():
    payload = {'new_cards': [
        {'key': 'n1', 'name': 'x', 'other_names': [f'и{i}' for i in range(12)] + ['я' * 81],
         'quotes': ['a' * 301, 'b', 'c', 'd']},
        {'key': 'n2', 'name': 'я' * 81, 'quotes': ['a']}, {'key': 'n3', 'name': 'y', 'quotes': []}],
        'card_updates': [{'id': 'c1', 'other_names': ['я' * 81, 'ок']}],
        'protagonist_candidates': [{'id': 'a', 'score': 1.5}, {'id': 'b', 'score': 0.4}, {'id': 'c', 'score': 0.3},
                                   {'id': 'd', 'score': 0.2}, {'id': 'e', 'score': 0.1}]}
    parsed = parse_extract(json.dumps(payload))
    assert [card.key for card in parsed.new_cards] == ['n1', 'n3']
    assert parsed.new_cards[0].other_names == [f'и{i}' for i in range(10)] and parsed.new_cards[0].quotes == ['b', 'c']
    assert parsed.new_cards[1].quotes == [] and parsed.card_updates[0].other_names == ['ок']
    assert [item.id for item in parsed.protagonist_candidates] == ['b', 'c', 'd']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_protagonist_sum_rounding_over_groups():
    st = state(ANNA)
    for score in (0.7, 0.2, 0.1):
        st = run(st, parse_extract(json.dumps({'protagonist_candidates': [{'id': 'c1', 'score': score}]})))
    assert st.scores['card-1'] < 1.0
    protagonist = finalize(st, {}, False)['protagonist']
    assert protagonist == {'ref': 'card-1', 'scores': [{'ref': 'card-1', 'score': 1.0}]}
