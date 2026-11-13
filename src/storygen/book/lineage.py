"""Scene lineage (BOOK-LINEAGE): which earlier scenes a scene's memory, context and dependencies stand on.

Direct predecessors of a scene in a structured book:
- the previous scene of the same arc;
- the first scene of an arc: the heads of the arcs of the same part that ended above it, or else the start of the part;
- the start of a part: the heads of all arcs of the nearest earlier part with scenes (none for the first part).
Ancestors are the transitive closure in reading order; heads are the predecessors that are not ancestors of one another.
For a flat book, a book with sequential arcs, and a book where some active scene has no known arc, the lineage is the
reading-order chain: every active scene above, and the previous one as the only head."""
from dataclasses import dataclass

from .structure import effective_structure


@dataclass(frozen=True)
class Lineage:
    heads: tuple[str, ...]
    ancestors: tuple[str, ...]  # reading order
    needs_merge: bool


def _active(scenes):
    return sorted((s for s in scenes if not s.trashed_at), key=lambda s: s.position)


def _chain(active):
    return {s.id: Lineage((active[i - 1].id,) if i else (), tuple(x.id for x in active[:i]), False) for i, s in enumerate(active)}


def lineage_map(story, scenes) -> dict:
    active = _active(scenes)
    if getattr(story, 'book_structure', None) is None:  # no structure, or a pure helper called without a story
        return _chain(active)
    structure = effective_structure(story, active)
    if structure.kind == 'flat' or any(s.id not in structure.arcs_of for s in active):
        return _chain(active)
    arcs_of, part_of = structure.arcs_of, structure.part_of_arc
    index = {s.id: i for i, s in enumerate(active)}
    last_of_arc = {}
    for s in active:
        for arc in arcs_of[s.id]:
            last_of_arc[arc] = s.id
    part_index = {p.id: i for i, p in enumerate(structure.parts)}
    ancestors: dict[str, set[str]] = {}
    result = {}
    previous_in_arc: dict[str, str] = {}
    for i, s in enumerate(active):
        predecessors = []
        for arc in arcs_of[s.id]:
            for p in _arc_predecessors(arc, i, structure, part_of, part_index, previous_in_arc, last_of_arc, index):
                if p not in predecessors:
                    predecessors.append(p)
        closure = set(predecessors)
        for p in predecessors:
            closure |= ancestors[p]
        heads = _heads(predecessors, ancestors, index)
        ancestors[s.id] = closure
        result[s.id] = Lineage(heads, tuple(sorted(closure, key=index.__getitem__)), len(heads) > 1)
        for arc in arcs_of[s.id]:
            previous_in_arc[arc] = s.id
    return result


def _heads(predecessors, ancestors, index) -> tuple[str, ...]:
    return tuple(sorted((p for p in predecessors if not any(p in ancestors[q] for q in predecessors if q != p)),
                        key=index.__getitem__))


def _arc_predecessors(arc, i, structure, part_of, part_index, previous_in_arc, last_of_arc, index) -> list[str]:
    """Direct predecessors through one arc of the scene at reading index `i`."""
    if arc in previous_in_arc:
        return [previous_in_arc[arc]]
    part = structure.parts[part_index[part_of[arc]]]
    ended = [last_of_arc[a.id] for a in part.arcs
             if a.id != arc and a.id in last_of_arc and index[last_of_arc[a.id]] < i]
    # The start of a part: the heads of the nearest earlier part that has scenes (an empty part is skipped).
    back = part_index[part.id] - 1
    while not ended and back >= 0:
        ended = [last_of_arc[a.id] for a in structure.parts[back].arcs if a.id in last_of_arc]
        back -= 1
    return ended


def merge_key(heads) -> str:
    """Key of a merge point: every scene with the same set of heads shares one merge (MEMORY-MERGE)."""
    return 'heads:' + ','.join(sorted(heads))


def book_end_heads(story, scenes) -> tuple[str, ...]:
    """Heads at the end of the book: the last scenes of the arcs of the last part with scenes that are not ancestors of
    one another, in reading order; one element means the book ends without a merge."""
    active = _active(scenes)
    if not active:
        return ()
    items = lineage_map(story, active)
    structure = effective_structure(story, active) if getattr(story, 'book_structure', None) is not None else None
    if structure is None or structure.kind == 'flat' or any(s.id not in structure.arcs_of for s in active):
        return (active[-1].id,)
    last_part = structure.part_of_arc[structure.arc_of[active[-1].id]]
    last_of_arc = {}
    for s in active:
        for arc in structure.arcs_of[s.id]:
            if structure.part_of_arc[arc] == last_part:
                last_of_arc[arc] = s.id
    index = {s.id: i for i, s in enumerate(active)}
    candidates = list(dict.fromkeys(last_of_arc.values()))
    ancestors = {scene_id: set(items[scene_id].ancestors) for scene_id in candidates}
    return _heads(candidates, ancestors, index)


def lineage(story, scenes, scene_id: str) -> Lineage:
    return lineage_map(story, scenes)[scene_id]


def previous_scenes(story, scenes, scene) -> list:
    """Ancestors of `scene` as scene objects in reading order; a scene outside the active lineage (trashed, not yet
    listed) gets every active scene above its position, as before the lineage."""
    active = _active(scenes)
    item = lineage_map(story, active).get(scene.id)
    if item is None:
        return [s for s in active if s.position < scene.position]
    wanted = set(item.ancestors)
    return [s for s in active if s.id in wanted]


def earlier_scenes(view, scene, *, peek: bool = False) -> list:
    """previous_scenes read through a repository or context view; `peek` reads without recording dependencies."""
    story = (view.peek_story if peek and hasattr(view, 'peek_story') else view.get_story)(scene.story_id)
    scenes = (view.peek_scenes if peek and hasattr(view, 'peek_scenes') else view.list_scenes)(scene.story_id)
    return previous_scenes(story, scenes, scene)
