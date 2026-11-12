"""BOOK-LINEAGE-S01/S02: scene lineage — heads, ancestors in reading order and the need for a merge (neutral examples)."""
from storygen.book.lineage import lineage, lineage_map, previous_scenes
from storygen.domain import Arc, BookStructure, Part, Scene, Story


def book(arcs_by_scene, parts=None):
    """`arcs_by_scene`: arc ids in reading order, e.g. 'A A B'; `parts`: [[arc ids], ...] (default: one part with all arcs)."""
    arcs = arcs_by_scene.split()
    order = list(dict.fromkeys(arcs))
    parts = parts or [order]
    structure = BookStructure(parts=[Part(id=f'p{i}', arcs=[Arc(id=a) for a in part]) for i, part in enumerate(parts, 1)])
    scenes = [Scene(id=f's{n}', story_id='b', title=f'Сцена {n}', position=n - 1) for n in range(1, len(arcs) + 1)]
    story = Story(id='b', title='Книга', book_structure=structure, scene_arcs={s.id: a for s, a in zip(scenes, arcs)})
    return story, scenes


def ids(*numbers):
    return tuple(f's{n}' for n in numbers)


def test_flat_book_is_every_scene_above():
    scenes = [Scene(id=f's{n}', story_id='b', title='С', position=n - 1) for n in range(1, 5)]
    story = Story(id='b', title='Книга')
    assert lineage(story, scenes, 's1') == lineage_map(story, scenes)['s1']
    assert lineage(story, scenes, 's1').heads == () and lineage(story, scenes, 's1').ancestors == ()
    assert lineage(story, scenes, 's4').heads == ids(3) and lineage(story, scenes, 's4').ancestors == ids(1, 2, 3)
    assert [s.id for s in previous_scenes(story, scenes, scenes[3])] == ['s1', 's2', 's3']


def test_sequential_arcs_and_parts_are_every_scene_above():
    story, scenes = book('A A B B C C', parts=[['A', 'B'], ['C']])
    for n, scene in enumerate(scenes, 1):
        item = lineage(story, scenes, scene.id)
        assert item.ancestors == ids(*range(1, n)) and item.heads == (ids(n - 1) if n > 1 else ()) and not item.needs_merge


def test_interleaved_arcs_isolate_streams():
    story, scenes = book('A B A B')
    assert lineage(story, scenes, 's2').heads == () and lineage(story, scenes, 's2').ancestors == ()
    assert lineage(story, scenes, 's3').heads == ids(1) and lineage(story, scenes, 's3').ancestors == ids(1)
    assert lineage(story, scenes, 's4').heads == ids(2) and lineage(story, scenes, 's4').ancestors == ids(2)
    assert [s.id for s in previous_scenes(story, scenes, scenes[3])] == ['s2']


def test_first_scene_of_an_arc_after_ended_arcs():
    # A continues below C1, so C1 gets only B, which ended above it.
    story, scenes = book('A B A C A')
    item = lineage(story, scenes, 's4')
    assert item.heads == ids(2) and item.ancestors == ids(2) and not item.needs_merge
    # Two ended arcs whose streams never met need a merge.
    story, scenes = book('A B A B C')
    item = lineage(story, scenes, 's5')
    assert item.heads == ids(3, 4) and item.ancestors == ids(1, 2, 3, 4) and item.needs_merge
    # A sequential arc inherits the ended one: no merge.
    story, scenes = book('A B C')
    assert lineage(story, scenes, 's3').heads == ids(2) and lineage(story, scenes, 's3').ancestors == ids(1, 2)


def test_part_start_merges_heads_of_the_previous_part():
    story, scenes = book('A B A B C C', parts=[['A', 'B'], ['C']])
    item = lineage(story, scenes, 's5')
    assert item.heads == ids(3, 4) and item.ancestors == ids(1, 2, 3, 4) and item.needs_merge
    assert lineage(story, scenes, 's6').heads == ids(5) and lineage(story, scenes, 's6').ancestors == ids(1, 2, 3, 4, 5)


def test_empty_arc_and_unknown_arc_fall_back():
    story, scenes = book('A A B', parts=[['A', 'X'], ['B']])  # arc X has no scenes
    assert lineage(story, scenes, 's3').heads == ids(2) and lineage(story, scenes, 's3').ancestors == ids(1, 2)
    story.scene_arcs.pop('s2')  # a scene without a known arc follows the reading order, and so does the scene after it
    assert lineage(story, scenes, 's2').ancestors == ids(1) and lineage(story, scenes, 's3').ancestors == ids(1, 2)
    trashed = Scene(id='t', story_id='b', title='Кошик', position=1, trashed_at='2026-11-13T00:00:00Z')
    assert [s.id for s in previous_scenes(story, scenes, trashed)] == ['s1']
