"""Reference lineage (PERF-001, #39): `book/lineage.py` as of 7a56d932, before the O(n) chain and the request-scoped
memo. Tests compare the optimised module against it; do not change it together with the module."""
from storygen.book.lineage import Lineage
from storygen.book.structure import effective_structure


def _active(scenes):
    return sorted((s for s in scenes if not s.trashed_at), key=lambda s: s.position)


def _chain(active):
    return {s.id: Lineage((active[i - 1].id,) if i else (), tuple(x.id for x in active[:i]), False) for i, s in enumerate(active)}


def reference_lineage_map(story, scenes) -> dict:
    active = _active(scenes)
    if getattr(story, 'book_structure', None) is None:
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


def _heads(predecessors, ancestors, index):
    return tuple(sorted((p for p in predecessors if not any(p in ancestors[q] for q in predecessors if q != p)),
                        key=index.__getitem__))


def _arc_predecessors(arc, i, structure, part_of, part_index, previous_in_arc, last_of_arc, index):
    if arc in previous_in_arc:
        return [previous_in_arc[arc]]
    part = structure.parts[part_index[part_of[arc]]]
    ended = [last_of_arc[a.id] for a in part.arcs
             if a.id != arc and a.id in last_of_arc and index[last_of_arc[a.id]] < i]
    back = part_index[part.id] - 1
    while not ended and back >= 0:
        ended = [last_of_arc[a.id] for a in structure.parts[back].arcs if a.id in last_of_arc]
        back -= 1
    return ended


def reference_book_end_heads(story, scenes):
    active = _active(scenes)
    if not active:
        return ()
    structure = effective_structure(story, active) if getattr(story, 'book_structure', None) is not None else None
    if structure is None or structure.kind == 'flat' or any(s.id not in structure.arcs_of for s in active):
        return (active[-1].id,)
    return reference_part_end_heads(story, active, structure.part_of_arc[structure.arc_of[active[-1].id]])


def reference_part_end_heads(story, scenes, part_id):
    active = _active(scenes)
    if not active:
        return ()
    structure = effective_structure(story, active) if getattr(story, 'book_structure', None) is not None else None
    if structure is None or structure.kind == 'flat' or any(s.id not in structure.arcs_of for s in active):
        return (active[-1].id,)
    items = reference_lineage_map(story, active)
    last_of_arc = {}
    for s in active:
        for arc in structure.arcs_of[s.id]:
            if structure.part_of_arc[arc] == part_id:
                last_of_arc[arc] = s.id
    index = {s.id: i for i, s in enumerate(active)}
    candidates = list(dict.fromkeys(last_of_arc.values()))
    ancestors = {scene_id: set(items[scene_id].ancestors) for scene_id in candidates}
    return _heads(candidates, ancestors, index)


def reference_previous_scenes(story, scenes, scene):
    active = _active(scenes)
    item = reference_lineage_map(story, active).get(scene.id)
    if item is None:
        return [s for s in active if s.position < scene.position]
    wanted = set(item.ancestors)
    return [s for s in active if s.id in wanted]
