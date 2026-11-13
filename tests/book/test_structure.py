"""BOOK-STRUCTURE: effective structure, shape limits and the sequential rule (pure, no storage)."""
import pytest

from storygen.book.structure import (IMPLICIT_ARC, IMPLICIT_PART, arc_before, check_sequential, effective_structure,
                                     validate_shape)
from storygen.domain import Arc, BookStructure, Part, Scene, Story


def story(structure=None, scene_arcs=None):
    return Story(id='s', title='T', book_structure=structure, scene_arcs=scene_arcs or {})


def scenes(n, trashed=()):
    return [Scene(id=f'c{i}', story_id='s', position=i, title=f'Scene {i + 1}', trashed_at='x' if i in trashed else None)
            for i in range(n)]


def two_arcs():
    return BookStructure(parts=[Part(id='p1', title='One', arcs=[Arc(id='a1', title='A'), Arc(id='a2', title='B')])])


def test_no_structure_is_one_implicit_arc_over_active_scenes():
    result = effective_structure(story(), scenes(3, trashed=(1,)))
    assert result.kind == 'flat' and not result.explicit
    assert [p.id for p in result.parts] == [IMPLICIT_PART] and [a.id for a in result.parts[0].arcs] == [IMPLICIT_ARC]
    assert result.arc_of == {'c0': IMPLICIT_ARC, 'c2': IMPLICIT_ARC}


def test_one_explicit_arc_is_flat_two_arcs_are_structured():
    one = BookStructure(parts=[Part(id='p1', arcs=[Arc(id='a1')])])
    assert effective_structure(story(one, {'c0': 'a1'}), scenes(1)).kind == 'flat'
    result = effective_structure(story(two_arcs(), {'c0': 'a1', 'c1': 'a2'}), scenes(2))
    assert result.kind == 'structured' and result.explicit and result.arc_of == {'c0': 'a1', 'c1': 'a2'}


def test_interleaved_arcs_and_unassigned_scenes_are_violations():
    assert check_sequential(two_arcs(), {'c0': 'a1', 'c1': 'a2', 'c2': 'a1'}, scenes(3))
    messages = check_sequential(two_arcs(), {'c0': 'a1'}, scenes(2))
    assert messages and 'Scene 2' in messages[0]


def test_ordered_arcs_empty_arcs_and_trashed_scenes_are_fine():
    assert check_sequential(two_arcs(), {'c0': 'a1', 'c1': 'a1', 'c2': 'a2'}, scenes(3)) == []
    assert check_sequential(two_arcs(), {'c0': 'a2'}, scenes(1)) == []
    # A trashed scene keeps a stale binding; only active scenes are ordered.
    assert check_sequential(two_arcs(), {'c0': 'a2', 'c1': 'a1', 'c2': 'a2'}, [s for s in scenes(3, trashed=(1,)) if not s.trashed_at]) == []


def test_parts_must_stay_contiguous():
    structure = BookStructure(parts=[Part(id='p1', arcs=[Arc(id='a1')]), Part(id='p2', arcs=[Arc(id='a2')])])
    assert check_sequential(structure, {'c0': 'a2', 'c1': 'a1'}, scenes(2))


def test_shape_limits():
    with pytest.raises(ValueError):validate_shape(BookStructure(parts=[Part(id='p1', arcs=[])]))
    with pytest.raises(ValueError):validate_shape(BookStructure(parts=[Part(id=f'p{i}', arcs=[Arc(id=f'a{i}')]) for i in range(201)]))
    with pytest.raises(ValueError):validate_shape(BookStructure(parts=[Part(id='p1', title='x' * 201, arcs=[Arc(id='a1')])]))
    with pytest.raises(ValueError):validate_shape(BookStructure(parts=[Part(id='p1', arcs=[Arc(id='a1'), Arc(id='a1')])]))
    validate_shape(two_arcs())


def test_arc_before_takes_the_previous_active_scene():
    bound = {'c0': 'a1', 'c1': 'a2'}
    active = scenes(2)
    assert arc_before(two_arcs(), bound, active, 0) == 'a1'
    assert arc_before(two_arcs(), bound, active, 1) == 'a1'
    assert arc_before(two_arcs(), bound, active, 2) == 'a2'
