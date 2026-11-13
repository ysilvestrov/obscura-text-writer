"""STORY-TIME-S02: an arc starts at the moment of its first active scene that is not a flashback (pure, no storage)."""
from storygen.book.story_time import arc_start, is_flashback
from storygen.domain import Arc, BookStructure, Part, Scene, Story
from storygen.memory.story_time import scene_moment


def book(beats, arcs, trashed=()):
    scenes = [Scene(id=f's{i}', story_id='b', position=i, title=f'Сцена {i + 1}', beats=text,
                    trashed_at='2026-11-13T00:00:00Z' if i in trashed else None) for i, text in enumerate(beats)]
    structure = BookStructure(parts=[Part(id='p1', title='Одна', arcs=[Arc(id='A'), Arc(id='B')])])
    return Story(id='b', title='Книга', book_structure=structure, scene_arcs={s.id: a for s, a in zip(scenes, arcs)}), scenes


def test_arc_start_is_the_first_scene_that_is_not_a_flashback():
    story, scenes = book(['Початок: Рік -20 (спогад)', 'Без позначки', 'Початок: Рік 1, День 3', 'Початок: Рік 2'], ['A', 'B', 'A', 'B'])
    assert is_flashback(scenes[0]) and not is_flashback(scenes[2])
    assert arc_start(story, scenes, 'A') == scene_moment('Початок: Рік 1, День 3')
    assert arc_start(story, scenes, 'B') is None


def test_arc_start_skips_trashed_scenes():
    story, scenes = book(['Початок: Рік 5', 'Початок: Рік 9', 'Початок: Рік 1', 'Початок: Рік 9'], ['A', 'B', 'A', 'B'], trashed={0})
    assert arc_start(story, scenes, 'A') == scene_moment('Початок: Рік 1')


def test_a_meeting_scene_can_open_its_arcs():
    story, scenes = book(['Початок: Рік 3', 'Початок: Рік 4'], [['A', 'B'], 'B'])
    assert arc_start(story, scenes, 'A') == scene_moment('Початок: Рік 3')
    assert arc_start(story, scenes, 'B') == scene_moment('Початок: Рік 3')
