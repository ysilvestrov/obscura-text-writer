"""Pure book structure rules (BOOK-STRUCTURE): the effective structure, shape limits and the sequential order.

The structure lives in the story payload and never enters a context or a dependency snapshot.
"""
from dataclasses import dataclass, field
from typing import Literal

from ..domain import Arc, BookStructure, Part

IMPLICIT_PART = 'implicit-part'
IMPLICIT_ARC = 'implicit-arc'
MAX_PARTS = 200
MAX_ARCS = 1000
MAX_TITLE = 200


@dataclass(frozen=True)
class EffectiveStructure:
    parts: list[Part]
    arc_of: dict[str, str]  # the first known arc of each scene
    kind: Literal['flat', 'structured']
    explicit: bool
    part_of_arc: dict[str, str] = field(default_factory=dict)
    arcs_of: dict[str, tuple[str, ...]] = field(default_factory=dict)  # every known arc; two or more for a meeting scene


def _active(scenes):
    return sorted((s for s in scenes if not s.trashed_at), key=lambda s: s.position)


def scene_arc_list(scene_arcs: dict, scene_id: str) -> list[str]:
    """Arcs of a scene binding: a string is one arc, a list a meeting scene; the only way to read `Story.scene_arcs`."""
    value = scene_arcs.get(scene_id)
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def canonical_arcs(arcs: list[str]) -> str | list[str]:
    """Stored form of a binding: one arc stays a string, so payloads of books without meeting scenes never change."""
    return arcs[0] if len(arcs) == 1 else list(arcs)


def arc_order(structure: BookStructure) -> dict[str, tuple[int, int]]:
    return {arc.id: (p, a) for p, part in enumerate(structure.parts) for a, arc in enumerate(part.arcs)}


def effective_structure(story, scenes) -> EffectiveStructure:
    active = _active(scenes)
    if story.book_structure is None:
        part = Part(id=IMPLICIT_PART, arcs=[Arc(id=IMPLICIT_ARC)])
        return EffectiveStructure([part], {s.id: IMPLICIT_ARC for s in active}, 'flat', False, {IMPLICIT_ARC: IMPLICIT_PART},
                                  {s.id: (IMPLICIT_ARC,) for s in active})
    parts = story.book_structure.parts
    arcs = sum(len(p.arcs) for p in parts)
    kind = 'structured' if len(parts) > 1 or arcs > 1 else 'flat'
    known = arc_order(story.book_structure)
    arcs_of = {}
    for s in active:
        arcs = tuple(a for a in scene_arc_list(story.scene_arcs, s.id) if a in known)
        if arcs:
            arcs_of[s.id] = arcs
    arc_of = {scene_id: arcs[0] for scene_id, arcs in arcs_of.items()}
    return EffectiveStructure(list(parts), arc_of, kind, True, {a.id: p.id for p in parts for a in p.arcs}, arcs_of)


def structure_kind(story, scenes) -> Literal['flat', 'structured']:
    return effective_structure(story, scenes).kind


def validate_shape(structure: BookStructure) -> None:
    if len(structure.parts) > MAX_PARTS:
        raise ValueError(f'Забагато частин: до {MAX_PARTS}')
    arcs = [arc for part in structure.parts for arc in part.arcs]
    if len(arcs) > MAX_ARCS:
        raise ValueError(f'Забагато арок: до {MAX_ARCS}')
    if not structure.parts:
        raise ValueError('Структура має містити хоча б одну частину')
    ids = [p.id for p in structure.parts] + [a.id for a in arcs]
    if len(ids) != len(set(ids)):
        raise ValueError('ID частин і арок мають бути унікальними')
    for number, part in enumerate(structure.parts, 1):
        if not part.arcs:
            raise ValueError(f'Частина {number} не має арок: у кожній частині лишається хоча б одна арка')
        if len(part.title) > MAX_TITLE or any(len(a.title) > MAX_TITLE for a in part.arcs):
            raise ValueError(f'Назва частини чи арки — до {MAX_TITLE} символів')


def _scene_label(scene, number):
    return f'сцена {number} «{scene.title}»'


def check_order(structure: BookStructure, scene_arcs: dict, active_scenes) -> list[str]:
    """Violations, empty when every active scene has a known arc, a meeting scene has two or more different arcs of one
    part, and parts never go back in structure order. Arcs of a part may interleave (BOOK-STRUCTURE, project 2)."""
    order = arc_order(structure)
    part_of = {arc.id: p for p, part in enumerate(structure.parts) for arc in part.arcs}
    part_titles = [p.title or f'Частина {i}' for i, p in enumerate(structure.parts, 1)]
    problems = []
    last = None
    last_label = None
    for number, scene in enumerate(_active(active_scenes), 1):
        arcs = scene_arc_list(scene_arcs, scene.id)
        label = _scene_label(scene, number)
        capital = f'{label[0].upper()}{label[1:]}'
        if not arcs or any(arc not in order for arc in arcs):
            problems.append(f'{capital} не має арки зі структури книги')
            continue
        if len(arcs) > 1 and (len(set(arcs)) != len(arcs) or len({part_of[a] for a in arcs}) != 1):
            problems.append(f'{capital} — сцена зустрічі: її арки мають бути різними й належати одній частині')
            continue
        part = part_of[arcs[0]]
        if last is not None and part < last:
            problems.append(f'{capital} з частини «{part_titles[part]}» стоїть після {last_label} з частини «{part_titles[last]}»: '
                            'частини мають іти по черзі')
        if last is None or part >= last:
            last, last_label = part, label
    return problems


def arc_after_meeting(arcs: list[str], before: str | None) -> str:
    """The arc a scene after a meeting scene continues: the arc that stood before the meeting when it is among the
    meeting's arcs, otherwise the first listed one."""
    return before if before in arcs else arcs[0]


def arc_before(structure: BookStructure, scene_arcs: dict, active_scenes, position: int) -> str:
    order = arc_order(structure)
    earlier = [s for s in _active(active_scenes)
               if s.position < position and scene_arc_list(scene_arcs, s.id) and all(a in order for a in scene_arc_list(scene_arcs, s.id))]
    if not earlier:
        return structure.parts[0].arcs[0].id
    arcs = scene_arc_list(scene_arcs, earlier[-1].id)
    if len(arcs) == 1:
        return arcs[0]
    single = [scene_arc_list(scene_arcs, s.id) for s in earlier[:-1]]
    before = next((a[0] for a in reversed(single) if len(a) == 1), None)
    return arc_after_meeting(arcs, before)
