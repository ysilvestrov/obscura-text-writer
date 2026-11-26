"""CHARACTER-EXTRACT-S12 (R-51, spec 2): places of scenes in the model answer — catalogue, paths, grounding, proposal."""
import pytest

from storygen.characters.extract import (
    CatalogueLocation, ExtractState, SceneLocation, SceneMeta, SceneProse, apply_group, finalize, location_text,
    parse_extract, short_ids)

P1 = 'Іван вийшов на полонину. У стаї пахло димом, а стариня мовчала.'
P2 = 'Марічка сиділа в хаті й чекала. Надворі падав сніг.'
GROUP = [SceneProse('sc1', 'v1', P1), SceneProse('sc2', 'v2', P2)]
POLONYNA = CatalogueLocation(ref='loc_a', path='Полонина', existing=True)
STAIA = CatalogueLocation(ref='loc_b', path='Полонина / Стая', existing=True)


def state(*locations):
    return ExtractState(locations=list(locations), scene_order=['sc1', 'sc2'])


def run(st, scenes):
    card_numbers, scene_numbers = short_ids(st, ['sc1', 'sc2'])
    response = parse_extract('{"scenes": %s}' % scenes)
    return apply_group(st, response, GROUP, scene_numbers=scene_numbers, card_numbers=card_numbers)


def places(st, scene_id):
    paths = {loc.ref: loc.path for loc in st.locations}
    return [(paths[item.ref], item.suggested) for item in st.scene_locations.get(scene_id, [])]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_catalogue_id_and_new_nested_path():
    st = run(state(POLONYNA), '[{"scene":"s1","locations":["l1","Полонина / Стая"]},{"scene":"s2","locations":["Село / Хата"]}]')
    assert places(st, 'sc1') == [('Полонина', True), ('Полонина / Стая', True)]
    assert places(st, 'sc2') == [('Село / Хата', True)]
    assert [(loc.ref, loc.path, loc.existing) for loc in st.locations] == [
        ('loc_a', 'Полонина', True), ('newloc1', 'Полонина / Стая', False), ('newloc2', 'Село / Хата', False)]
    assert location_text(st, 'uk').splitlines() == ['l1: Полонина', 'l2: Полонина / Стая', 'l3: Село / Хата']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_catalogue_id_inside_a_path_expands_and_a_repeated_parent_part_drops():
    st = run(state(POLONYNA, STAIA), '[{"scene":"s1","locations":["l1 / Стая","l2 / Стая","L1 / Ватра"]}]')
    assert places(st, 'sc1') == [('Полонина / Стая', True), ('Полонина / Ватра', False)]
    assert [loc.ref for loc in st.locations] == ['loc_a', 'loc_b', 'newloc1']  # «l1 / Стая» is the known card l2


@pytest.mark.req('CHARACTER-EXTRACT')
def test_unknown_catalogue_id_is_dropped():
    st = run(state(POLONYNA), '[{"scene":"s1","locations":["l7","l9 / Стая","l1"]}]')
    assert places(st, 'sc1') == [('Полонина', True)]
    assert len(st.locations) == 1


@pytest.mark.req('CHARACTER-EXTRACT')
def test_over_three_places_are_trimmed_not_rejected():
    st = run(state(), '[{"scene":"s1","locations":["Полонина, Стая","Ліс","Річка","Гора"]}]')
    assert [path for path, _ in places(st, 'sc1')] == ['Полонина', 'Стая', 'Ліс']
    long = run(state(), '[{"scene":"s1","locations":["%s","Полонина"]}]' % ('д' * 121))
    assert [path for path, _ in places(long, 'sc1')] == ['Полонина']


@pytest.mark.req('CHARACTER-EXTRACT')
def test_a_place_absent_from_the_scene_prose_is_unsuggested():
    st = run(state(POLONYNA), '[{"scene":"s2","locations":["l1","Хата"]}]')
    assert places(st, 'sc2') == [('Полонина', False), ('Хата', True)]  # known to the book, not named in this scene


@pytest.mark.req('CHARACTER-EXTRACT')
def test_four_letter_words_match_only_close_forms():
    st = run(state(), '[{"scene":"s1","locations":["Ста"]},{"scene":"s2","locations":["Хата"]}]')
    assert places(st, 'sc2') == [('Хата', True)]  # «хаті»
    prose = [SceneProse('sc1', 'v1', 'Стариня сиділа біля печі.')]
    card_numbers, scene_numbers = short_ids(state(), ['sc1'])
    alone = apply_group(state(), parse_extract('{"scenes":[{"scene":"s1","locations":["Стая"]}]}'), prose,
                        scene_numbers=scene_numbers, card_numbers=card_numbers)
    assert places(alone, 'sc1') == [('Стая', False)]  # «ста» does not find «стариня»


@pytest.mark.req('CHARACTER-EXTRACT')
def test_answer_without_locations_stays_valid():
    st = run(state(POLONYNA), '[{"scene":"s1","participants":[]}]')
    assert st.scene_locations == {'sc1': []} and len(st.locations) == 1


def meta(scene_id, eligible=True, locations=()):
    return SceneMeta(scene_id, False, [], location_eligible=eligible, locations=list(locations))


@pytest.mark.req('CHARACTER-EXTRACT')
def test_finalize_set_add_and_ineligible():
    st = state(POLONYNA, CatalogueLocation(ref='newloc1', path='Село / Хата'))
    st.scene_locations = {'sc1': [SceneLocation(ref='loc_a', suggested=True), SceneLocation(ref='newloc1', suggested=False)],
                          'sc2': [SceneLocation(ref='loc_a', suggested=True)], 'sc3': [SceneLocation(ref='loc_a')]}
    st.scene_order = ['sc1', 'sc2', 'sc3']
    result = finalize(st, {'sc1': meta('sc1'), 'sc2': meta('sc2', locations=['loc_a']), 'sc3': meta('sc3', eligible=False)},
                      False)
    assert result['locations'] == [{'scene_id': 'sc1', 'mode': 'set', 'places': [
        {'ref': 'loc_a', 'path': 'Полонина', 'new': False, 'suggested': True},
        {'ref': 'newloc1', 'path': 'Село / Хата', 'new': True, 'suggested': False}]}]


@pytest.mark.req('CHARACTER-EXTRACT')
def test_finalize_compares_places_by_canonical_card():
    st = state(POLONYNA, CatalogueLocation(ref='newloc1', path='Полонина стара'), CatalogueLocation(ref='newloc2', path='Ліс'))
    st.scene_locations = {'sc1': [SceneLocation(ref='loc_a'), SceneLocation(ref='newloc1'), SceneLocation(ref='newloc2')]}
    # `newloc1` names a card merged into loc_m, which the scene already holds; loc_a is merged into loc_m as well.
    ids = {'loc_a': 'loc_m', 'newloc1': 'loc_m', 'newloc2': 'loc_l'}
    result = finalize(st, {'sc1': meta('sc1', locations=['loc_m'])}, False, place_ids=ids)
    assert result['locations'] == [{'scene_id': 'sc1', 'mode': 'add', 'places': [
        {'ref': 'newloc2', 'path': 'Ліс', 'new': True, 'suggested': True}]}]
