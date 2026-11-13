"""BOOK-LINEAGE-S04: arc protagonist — the tracked characters of a scene are the protagonists of its arcs (neutral examples)."""
import json

from storygen.book.protagonists import has_explicit_protagonists, scene_tracked
from storygen.characters.models import load_characters
from storygen.domain import Arc, BookStructure, Part, Scene, Story
from storygen.memory.core import tracked_characters

HERO = 'Роль: Головна героїня'


def cards():
    data = [dict(schema_version=2, id=i, name=n, entries=[dict(id='e' + i, text=HERO if i == 'A' else 'Опис', availability='timeless', origin='author')])
            for i, n in [('A', 'Анна'), ('B', 'Богдан')]]
    return load_characters(json.dumps(data, ensure_ascii=False))


def scenes(count):
    return [Scene(id=f's{n}', story_id='b', title=f'Сцена {n}', position=n - 1, character_ids=['A', 'B']) for n in range(1, count + 1)]


def book(protagonist=None):
    """Two parts with one arc each: X (s1, s2) and Y (s3, s4); Y may have an explicit protagonist."""
    structure = BookStructure(parts=[Part(id='p1', arcs=[Arc(id='X')]), Part(id='p2', arcs=[Arc(id='Y', protagonist_id=protagonist)])])
    items = scenes(4)
    story = Story(id='b', title='Книга', book_structure=structure, scene_arcs={'s1': 'X', 's2': 'X', 's3': 'Y', 's4': 'Y'})
    return story, items


def test_flat_book_tracks_the_book_hero():
    items = scenes(2)
    story = Story(id='b', title='Книга')
    assert scene_tracked(story, cards(), items, items[1]) == tracked_characters(cards(), items) == ['A']


def test_arc_protagonist_overrides_the_book_hero():
    story, items = book('B')
    assert [scene_tracked(story, cards(), items, s) for s in items] == [['A'], ['A'], ['B'], ['B']]


def test_missing_card_falls_back_to_the_book_hero():
    story, items = book('Z')
    assert scene_tracked(story, cards(), items, items[2]) == ['A']


def test_scene_without_a_known_arc_and_trashed_scene():
    story, items = book('B')
    story.scene_arcs.pop('s3')
    assert scene_tracked(story, cards(), items, items[2]) == ['A']
    trashed = Scene(id='t', story_id='b', title='Кошик', position=4, trashed_at='2026-11-13T00:00:00Z')
    assert scene_tracked(story, cards(), items, trashed) == ['A']


def test_trashed_scene_keeps_its_arc_but_tracks_the_book_hero():
    # Cross-review: the trash keeps the arc binding; a trashed scene still tracks the inferred hero (spec).
    story, items = book('B')
    items[3] = items[3].model_copy(update={'trashed_at': '2026-11-13T00:00:00Z'})
    assert story.scene_arcs['s4'] == 'Y' and scene_tracked(story, cards(), items, items[3]) == ['A']


def test_explicit_flag():
    assert not has_explicit_protagonists(Story(id='b', title='Книга'))
    assert not has_explicit_protagonists(book()[0])
    assert has_explicit_protagonists(book('B')[0])
