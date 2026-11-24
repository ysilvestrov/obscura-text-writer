"""CHARACTER-NAMES (#215): other names of a card, the name current in a scene and ambiguity."""
from types import SimpleNamespace
from storygen.characters.models import CharacterRecord
from storygen.characters.names import other_names_line, card_names, scene_name, scene_names, scene_match_names, name_warnings
from storygen.scene_description import resolve_participants


def card(cid, name, *entries):
    rows = [dict(id=f'{cid}{i}', text=text, availability='from_scene' if anchor else 'timeless',
                 available_from_scene_id=anchor, origin='author') for i, (text, anchor) in enumerate(entries)]
    return CharacterRecord.model_validate(dict(schema_version=2, id=cid, name=name, entries=rows))


def scene(sid, position):
    return SimpleNamespace(id=sid, story_id='s', position=position, character_ids=[], trashed_at=None)


SCENES = [scene(f's{i}', i) for i in range(10)]  # s6 is the 7th scene


def host():
    return card('H', 'Хазяїн', ('Вік: 40', None), ("Інше ім'я: Джон", 's6'))


def test_marker_line_variants():
    assert other_names_line("Інше ім'я: Джон") == ['Джон']
    assert other_names_line('- **Інші імена:** Незнайомець, Хазяїн') == ['Незнайомець', 'Хазяїн']
    assert other_names_line('Інше ім’я: Джон') == ['Джон']
    assert other_names_line('Також відома як: Ліна') == ['Ліна']
    assert other_names_line('Other names: John, Boss') == ['John', 'Boss']
    assert other_names_line('Also known as: John') == ['John']
    assert other_names_line('AKA: John') == ['John']
    assert other_names_line('Інше ім\'я: —') == []
    assert other_names_line('Вік: 40') is None


def test_card_names_keep_order_without_repeats():
    item = card('H', 'Хазяїн', ("Інші імена: Джон, хазяїн", None), ("Інше ім'я: Джон", 's6'))
    assert card_names(item) == ['Хазяїн', 'Джон']


def test_every_name_resolves_in_any_scene():
    cards = [host(), card('J', 'Юлія', ('Знайома з: Джон', None))]
    assert resolve_participants(['Джон', 'хазяїн', 'Юлія'], cards) == (['H', 'J'], [])


def boss():
    return card('B', 'Бос', ("Інше ім'я: Джон", None))


def test_name_shared_by_two_cards_is_ambiguous_and_warned():
    # CHARACTER-NAMES-S03: two other names, or two card names, stay ambiguous.
    cards = [host(), boss()]
    assert resolve_participants(['Джон'], cards) == ([], ['Неоднозначне ім’я: Джон'])
    assert resolve_participants(['Хазяїн'], cards) == (['H'], [])
    assert name_warnings(cards) == ['Ім’я «Джон» мають кілька карток: Хазяїн, Бос; у плані воно не розпізнається.']
    twins = [card('A', 'Джон', ('x', None)), card('C', 'джон', ('x', None)), host()]
    assert resolve_participants(['Джон'], twins) == ([], ['Неоднозначне ім’я: Джон'])
    assert name_warnings(twins) == ['Ім’я «Джон» мають кілька карток: Джон, джон; у плані воно не розпізнається.']
    assert name_warnings([host()]) == []


def test_card_name_wins_over_an_other_name_of_another_card():
    # CHARACTER-NAMES-S06: «Айя» and «Айя-бот» with «Інше ім'я: Айя».
    cards = [card('A', 'Айя', ('Агентка', None)), card('R', 'Айя-бот', ("Інше ім'я: Айя", None))]
    assert resolve_participants(['Айя', 'айя-бот'], cards) == (['A', 'R'], [])
    assert name_warnings(cards) == ['Ім’я «Айя» є основним ім’ям картки «Айя» та іншим ім’ям карток: Айя-бот; у плані воно означає основну картку.']
    assert name_warnings(cards + [card('Q', 'Квін', ("Інше ім'я: Айя", None))])[-1].endswith('іншим ім’ям карток: Айя-бот, Квін; у плані воно означає основну картку.')


def test_current_name_follows_the_latest_available_marker():
    item = card('H', 'Незнайомець', ("Інше ім'я: Хазяїн", 's2'), ("Інше ім'я: Джон", 's6'), ("Інше ім'я: Бос", None))
    active = {s.id: s for s in SCENES}
    assert scene_name(item, active, SCENES[1]) == ('Незнайомець', ['Бос'])
    assert scene_name(item, active, SCENES[3]) == ('Хазяїн', ['Незнайомець', 'Бос'])
    assert scene_name(item, active, SCENES[8]) == ('Джон', ['Незнайомець', 'Хазяїн', 'Бос'])


def test_scene_name_dicts_and_unmarked_cards():
    cards = [host(), card('J', 'Юлія', ('x', None))]
    assert scene_names(cards, SCENES, SCENES[5]) == {'H': 'Хазяїн', 'J': 'Юлія'}
    assert scene_names(cards, SCENES, SCENES[6]) == {'H': 'Джон', 'J': 'Юлія'}
    assert scene_match_names(cards, SCENES, SCENES[5]) == {'H': 'Хазяїн', 'J': 'Юлія'}
    assert scene_match_names(cards, SCENES, SCENES[6]) == {'H': 'Джон, Хазяїн', 'J': 'Юлія'}


def test_other_name_works_in_acquaintance_narrator_and_arc_protagonist_lines():
    from storygen.characters.acquaintance import pre_story_known
    from storygen.narration import parse_narrator
    from storygen.storage.book_structure import _apply_protagonists
    cards = [host(), card('J', 'Юлія', ('Знайома з: Джон', None))]
    assert pre_story_known(cards, SCENES, 's1', 'H') == ({'J'}, [])
    assert parse_narrator('перша особа, Джон', cards)[0].character_id == 'H'
    arc = SimpleNamespace(id='a1', protagonist_id=None)
    structure = SimpleNamespace(parts=[SimpleNamespace(arcs=[arc])])
    assert _apply_protagonists(structure, [('a1', 'Джон')], cards) == ([], [])
    assert arc.protagonist_id == 'H'


def test_acquaintance_names_a_shared_other_name_ambiguous_and_arc_skips_it():
    from storygen.characters.acquaintance import pre_story_known
    from storygen.storage.book_structure import _apply_protagonists
    cards = [boss(), host(), card('J', 'Юлія', ('Знайома з: Джон', None))]
    known, warnings = pre_story_known(cards, SCENES, 's1', 'J')
    assert known == set() and warnings == ['У картці «Юлія» позначка «Знайомий з:» називає «Джон», але так названо кілька карток; перейменуйте одну з них, щоб ім’я було однозначним.']
    arc = SimpleNamespace(id='a1', protagonist_id=None)
    _apply_protagonists(SimpleNamespace(parts=[SimpleNamespace(arcs=[arc])]), [('a1', 'Джон')], cards)
    assert arc.protagonist_id is None


def test_card_name_wins_in_acquaintance_protagonist_and_narrator_lines():
    # CHARACTER-NAMES-S06
    from storygen.characters.acquaintance import pre_story_known
    from storygen.narration import parse_narrator
    from storygen.storage.book_structure import _apply_protagonists
    cards = [card('A', 'Джон', ('x', None)), host(), card('J', 'Юлія', ('Знайома з: Джон', None))]
    assert pre_story_known(cards, SCENES, 's1', 'J') == ({'A'}, [])
    assert parse_narrator('перша особа, Джон', cards)[0].character_id == 'A'
    arc = SimpleNamespace(id='a1', protagonist_id=None)
    assert _apply_protagonists(SimpleNamespace(parts=[SimpleNamespace(arcs=[arc])]), [('a1', 'Джон')], cards) == ([], [])
    assert arc.protagonist_id == 'A'
    from storygen.narration import effective_narrator, narrator_value
    plan = SimpleNamespace(beats='Сцена 1: Ворота\nОповідач: перша особа, Джон', narrator=None)
    assert narrator_value(effective_narrator(plan, cards)[0]) == 'first:A'


def test_new_scene_cast_line_writes_an_id_only_for_an_ambiguous_name():
    from storygen.storage.scene_metadata import cast_names
    assert cast_names(['H'], [host()]) == 'Хазяїн'
    assert cast_names(['A', 'H'], [card('A', 'Джон', ('x', None)), host()]) == 'Джон, Хазяїн'
    assert cast_names(['A', 'C'], [card('A', 'Джон', ('x', None)), card('C', 'Джон', ('x', None))]) == 'A, C'
    assert cast_names(['H', 'B'], [host(), boss()]) == 'Хазяїн, Бос'
