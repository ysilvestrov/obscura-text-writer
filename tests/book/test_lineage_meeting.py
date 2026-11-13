"""BOOK-LINEAGE-S02: meeting scenes, shared merge points and the end of the book (neutral examples)."""
from storygen.book.lineage import Lineage, book_end_heads, lineage, merge_key
from storygen.domain import Arc, BookStructure, Part, Scene, Story


def book(arcs_by_scene, parts):
    """`arcs_by_scene`: 'A B A+B A' — a '+' joins the arcs of a meeting scene; `parts`: [[arc ids], ...]."""
    tokens = arcs_by_scene.split()
    structure = BookStructure(parts=[Part(id=f'p{i}', arcs=[Arc(id=a) for a in part]) for i, part in enumerate(parts, 1)])
    scenes = [Scene(id=f's{n}', story_id='b', title=f'Сцена {n}', position=n - 1) for n in range(1, len(tokens) + 1)]
    arcs = {s.id: (t if '+' not in t else t.split('+')) for s, t in zip(scenes, tokens)}
    return Story(id='b', title='Книга', book_structure=structure, scene_arcs=arcs), scenes


def ids(*numbers):
    return tuple(f's{n}' for n in numbers)


def test_interleaved_arcs_have_own_chains():
    story, scenes = book('A B A B', [['A', 'B']])
    assert lineage(story, scenes, 's4') == Lineage(ids(2), ids(2), False)
    assert lineage(story, scenes, 's3') == Lineage(ids(1), ids(1), False)


def test_meeting_scene_merges_arc_heads():
    story, scenes = book('A B A+B A', [['A', 'B']])
    assert lineage(story, scenes, 's3') == Lineage(ids(1, 2), ids(1, 2), True)
    assert lineage(story, scenes, 's4') == Lineage(ids(3), ids(1, 2, 3), False)


def test_meeting_scene_with_an_arc_that_has_not_started():
    # B has no scene above the meeting: its start rule gives the heads of ended arcs — none here — so only A's head counts.
    story, scenes = book('A A+B B', [['A', 'B']])
    assert lineage(story, scenes, 's2') == Lineage(ids(1), ids(1), False)
    assert lineage(story, scenes, 's3') == Lineage(ids(2), ids(1, 2), False)


def test_part_start_after_interleaved_arcs_shares_one_merge_point():
    # B starts while A goes on (A's last scene is below B's first), so A and B interleave.
    story, scenes = book('A B A B C D C D', [['A', 'B'], ['C', 'D']])
    first, second = lineage(story, scenes, 's5'), lineage(story, scenes, 's6')
    assert first == second == Lineage(ids(3, 4), ids(1, 2, 3, 4), True)
    assert merge_key(first.heads) == merge_key(tuple(reversed(second.heads))) == 'heads:s3,s4'


def test_book_end_heads():
    story, scenes = book('A B A B', [['A', 'B']])
    assert book_end_heads(story, scenes) == ids(3, 4)
    story, scenes = book('A A B B', [['A', 'B']])
    assert book_end_heads(story, scenes) == ids(4)
    story, scenes = book('A B A B C', [['A', 'B'], ['C']])
    assert book_end_heads(story, scenes) == ids(5)


def test_book_end_heads_of_a_flat_book_is_the_last_scene():
    scenes = [Scene(id=f's{n}', story_id='b', title='С', position=n - 1) for n in range(1, 4)]
    assert book_end_heads(Story(id='b', title='Книга'), scenes) == ids(3)
    assert book_end_heads(Story(id='b', title='Книга'), []) == ()
