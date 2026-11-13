"""BOOK-LINEAGE-S04 / BOOK-STRUCTURE-S04: the plan line «Протагоніст:» sets the arc protagonist by card name (neutral examples)."""
from storygen.authoring.imports import SourceFile, import_sources
from storygen.domain import StoryCreate
from storygen.plan_sections import split_book_plan
from storygen.storage.repository import Repository

CARDS = """## Персонажі

## Анна
Мандрівниця.

## Богдан
Перевізник.
"""

PLAN = '''# Частина 1: Берег

## Сцена 1: Ранок
Арка: Берег
Анна чекає.

# Частина 2: Річка

## Сцена 2: Пором
Арка: Пором
Протагоніст: **Богдан**
Богдан відчалює.

## Сцена 3: Туман
{line}Богдан править.
'''

UNKNOWN = 'Протагоніст «Ніхто» не знайдений серед карток; протагоніста арки не задано.'


def files(*items):
    return [SourceFile(name='characters.md' if kind else 'plan.md', raw=text.encode(), kind='source_characters' if kind else 'source_plan')
            for text, kind in items]


def arcs(repo, story_id):
    return [(arc.title, arc.protagonist_id) for part in repo.get_story(story_id).book_structure.parts for arc in part.arcs]


def card_id(repo, story_id, name):
    from storygen.characters.models import load_characters
    story = repo.get_story(story_id)
    return next(c.id for c in load_characters(repo.read_text(story.characters_version_id)) if c.name == name)


def story(tmp_path):
    repo = Repository(tmp_path)
    return repo, repo.create_story(StoryCreate(title='Книга'))


def test_protagonist_line_is_cut_from_the_plan():
    _, sections, found = split_book_plan(PLAN.format(line=''), 'Сцена')
    assert found and [s.protagonist_name for s in sections] == [None, 'Богдан', None]
    assert 'Протагоніст' not in ''.join(s.section.text for s in sections)


def test_import_sets_the_protagonist_of_a_new_arc(tmp_path):
    repo, item = story(tmp_path)
    import_sources(repo, item.id, files((CARDS, True)))
    result = import_sources(repo, item.id, files((PLAN.format(line=''), False)))
    assert arcs(repo, item.id) == [('Берег', None), ('Пором', card_id(repo, item.id, 'Богдан'))]
    assert not any('Протагоніст' in w or 'протагоніст' in w for w in result.warnings)


def test_unknown_name_warns_and_sets_nothing(tmp_path):
    repo, item = story(tmp_path)
    import_sources(repo, item.id, files((CARDS, True)))
    result = import_sources(repo, item.id, files((PLAN.format(line='').replace('**Богдан**', 'Ніхто'), False)))
    assert UNKNOWN in result.warnings and arcs(repo, item.id) == [('Берег', None), ('Пором', None)]


def test_cards_file_after_the_plan_resolves_at_the_end(tmp_path):
    repo, item = story(tmp_path)
    result = import_sources(repo, item.id, files((PLAN.format(line=''), False), (CARDS, True)))
    assert arcs(repo, item.id)[1] == ('Пором', card_id(repo, item.id, 'Богдан'))
    assert not any('Протагоніст' in w for w in result.warnings)


def test_other_name_for_an_arc_with_a_protagonist_warns(tmp_path):
    repo, item = story(tmp_path)
    import_sources(repo, item.id, files((CARDS, True)))
    result = import_sources(repo, item.id, files((PLAN.format(line='Протагоніст: Анна\n'), False)))
    assert 'Арка вже має протагоніста; рядок «Протагоніст: Анна» пропущено.' in result.warnings
    assert arcs(repo, item.id)[1] == ('Пором', card_id(repo, item.id, 'Богдан'))


def test_same_name_again_is_silent(tmp_path):
    repo, item = story(tmp_path)
    import_sources(repo, item.id, files((CARDS, True)))
    result = import_sources(repo, item.id, files((PLAN.format(line='Протагоніст: Богдан\n'), False)))
    assert not any('Протагоніст' in w for w in result.warnings)


def test_edition_without_long_prose_keeps_the_line(tmp_path, store_edition):
    repo, item = story(tmp_path)
    import_sources(repo, item.id, files((PLAN.format(line=''), False)))
    scenes = repo.list_scenes(item.id)
    assert repo.get_story(item.id).book_structure is None and 'Протагоніст' in scenes[1].beats
