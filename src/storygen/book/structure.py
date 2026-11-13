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
    arc_of: dict[str, str]
    kind: Literal['flat', 'structured']
    explicit: bool
    part_of_arc: dict[str, str] = field(default_factory=dict)


def _active(scenes):
    return sorted((s for s in scenes if not s.trashed_at), key=lambda s: s.position)


def arc_order(structure: BookStructure) -> dict[str, tuple[int, int]]:
    return {arc.id: (p, a) for p, part in enumerate(structure.parts) for a, arc in enumerate(part.arcs)}


def effective_structure(story, scenes) -> EffectiveStructure:
    active = _active(scenes)
    if story.book_structure is None:
        part = Part(id=IMPLICIT_PART, arcs=[Arc(id=IMPLICIT_ARC)])
        return EffectiveStructure([part], {s.id: IMPLICIT_ARC for s in active}, 'flat', False, {IMPLICIT_ARC: IMPLICIT_PART})
    parts = story.book_structure.parts
    arcs = sum(len(p.arcs) for p in parts)
    kind = 'structured' if len(parts) > 1 or arcs > 1 else 'flat'
    known = arc_order(story.book_structure)
    arc_of = {s.id: story.scene_arcs[s.id] for s in active if story.scene_arcs.get(s.id) in known}
    return EffectiveStructure(list(parts), arc_of, kind, True, {a.id: p.id for p in parts for a in p.arcs})


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


def check_sequential(structure: BookStructure, scene_arcs: dict, active_scenes) -> list[str]:
    """Violations, empty when every active scene has a known arc and arcs never go back in structure order."""
    order = arc_order(structure)
    titles = {a.id: a.title or f'Арка {i}' for i, a in enumerate((a for p in structure.parts for a in p.arcs), 1)}
    problems = []
    last = None
    last_label = None
    for number, scene in enumerate(_active(active_scenes), 1):
        arc = scene_arcs.get(scene.id)
        label = _scene_label(scene, number)
        if arc not in order:
            problems.append(f'{label[0].upper()}{label[1:]} не має арки зі структури книги')
            continue
        if last is not None and order[arc] < order[last]:
            problems.append(f'{label[0].upper()}{label[1:]} в арці «{titles[arc]}» стоїть після {last_label} з арки «{titles[last]}»: '
                            'арки й частини мають іти по черзі')
        if last is None or order[arc] >= order[last]:
            last, last_label = arc, label
    return problems


def arc_before(structure: BookStructure, scene_arcs: dict, active_scenes, position: int) -> str:
    order = arc_order(structure)
    earlier = [s for s in _active(active_scenes) if s.position < position and scene_arcs.get(s.id) in order]
    if earlier:
        return scene_arcs[earlier[-1].id]
    return structure.parts[0].arcs[0].id
