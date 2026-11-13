"""BOOK-STRUCTURE, project 2: interleaved arcs of a part and meeting scenes (pure, no storage)."""
from storygen.book.structure import arc_before, canonical_arcs, check_order, effective_structure, scene_arc_list
from storygen.domain import Arc, BookStructure, Part, Scene, Story


def scenes(n):
    return [Scene(id=f'c{i}', story_id='s', position=i, title=f'Scene {i + 1}') for i in range(n)]


def book():
    return BookStructure(parts=[Part(id='p1', title='One', arcs=[Arc(id='a'), Arc(id='b')]),
                                Part(id='p2', title='Two', arcs=[Arc(id='c')])])


def test_interleaved_arcs_are_allowed():
    assert check_order(book(), {'c0': 'a', 'c1': 'b', 'c2': 'a', 'c3': 'b'}, scenes(4)) == []


def test_parts_must_stay_contiguous():
    problems = check_order(book(), {'c0': 'a', 'c1': 'c', 'c2': 'b'}, scenes(3))
    assert len(problems) == 1 and 'Scene 3' in problems[0]


def test_meeting_scene_needs_two_arcs_of_one_part():
    assert check_order(book(), {'c0': ['a', 'b']}, scenes(1)) == []
    assert check_order(book(), {'c0': ['a', 'a']}, scenes(1))
    assert check_order(book(), {'c0': ['a', 'c']}, scenes(1))
    assert check_order(book(), {'c0': ['a', 'zz']}, scenes(1))


def test_scene_arc_list_and_canonical_form():
    assert scene_arc_list({'x': 'a', 'y': ['a', 'b']}, 'x') == ['a']
    assert scene_arc_list({'x': 'a', 'y': ['a', 'b']}, 'y') == ['a', 'b']
    assert scene_arc_list({}, 'x') == []
    assert canonical_arcs(['a']) == 'a' and canonical_arcs(['a', 'b']) == ['a', 'b']


def test_effective_structure_lists_meeting_arcs():
    story = Story(id='s', title='T', book_structure=book(), scene_arcs={'c0': 'a', 'c1': ['a', 'b']})
    result = effective_structure(story, scenes(2))
    assert result.arcs_of == {'c0': ('a',), 'c1': ('a', 'b')} and result.arc_of == {'c0': 'a', 'c1': 'a'}


def test_new_scene_after_meeting_scene_continues_the_arc_before_it():
    assert arc_before(book(), {'c0': 'b', 'c1': ['a', 'b']}, scenes(2), 2) == 'b'
    assert arc_before(book(), {'c0': 'c', 'c1': ['a', 'b']}, scenes(2), 2) == 'a'
