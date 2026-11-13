"""BOOK-STRUCTURE-S04 (harness of MEMORY-MERGE): the plan line «Арки: А, Б» makes a meeting scene (neutral examples)."""
from storygen.authoring.imports import SourceFile, import_sources
from storygen.book.structure import scene_arc_list
from storygen.domain import StoryCreate
from storygen.plan_sections import split_book_plan
from storygen.storage.repository import Repository


def plan(*scenes):
    body = '# Частина 1: Місто\n\n'
    for n, line in enumerate(scenes, 1):
        body += f'## Сцена {n}: Подія {n}\n{line}Анна йде містом.\n\n'
    return body


def imported(tmp_path, text):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    import_sources(repo, story.id, [SourceFile(name='plan.md', raw=text.encode(), kind='source_plan')])
    story = repo.get_story(story.id)
    titles = {a.id: a.title for p in story.book_structure.parts for a in p.arcs} if story.book_structure else {}
    scenes = repo.list_scenes(story.id)
    return [[titles[a] for a in scene_arc_list(story.scene_arcs, s.id)] for s in scenes], scenes


def test_arcs_line_makes_a_meeting_scene(tmp_path):
    arcs, scenes = imported(tmp_path, plan('Арка: Дорога\n', 'Арка: Місто\n', '**Арки:** Дорога; Місто\n'))
    assert arcs == [['Дорога'], ['Місто'], ['Дорога', 'Місто']]
    assert 'Арки' not in scenes[2].beats


def test_scene_after_meeting_returns_to_the_arc_before_it(tmp_path):
    arcs, _ = imported(tmp_path, plan('Арка: Дорога\n', 'Арка: Місто\n', 'Арки: Дорога, Місто\n', ''))
    assert arcs[3] == ['Місто']


def test_scene_after_meeting_takes_the_first_listed_arc(tmp_path):
    arcs, _ = imported(tmp_path, plan('Арка: Дорога\n', 'Арка: Місто\n', 'Арка: Ліс\n', 'Арки: Дорога, Місто\n', ''))
    assert arcs[4] == ['Дорога']


def test_single_title_in_arcs_line_is_one_arc(tmp_path):
    repo_arcs, _ = imported(tmp_path, plan('Арки: Дорога\n', 'Арки: Дорога, Дорога\n'))
    assert repo_arcs == [['Дорога'], ['Дорога']]


def test_arcs_line_is_not_an_arc_line():
    _, sections, found = split_book_plan(plan('Arcs: Road, Town\n'), 'Сцена')
    assert found and sections[0].arc_titles == ('Road', 'Town') and sections[0].arc_title == 'Road'


def test_edition_without_long_prose_keeps_the_arcs_line(tmp_path, store_edition):
    arcs, scenes = imported(tmp_path, plan('Арки: Дорога, Місто\n'))
    assert arcs == [[]] and 'Арки: Дорога, Місто' in scenes[0].beats
