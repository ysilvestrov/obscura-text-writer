"""BOOK-LINEAGE-S04: tracked characters of a scene — the protagonists of its arcs. Pure, no IO.

An arc without an explicit protagonist, or with one whose card is gone, takes the inferred protagonist of the book;
a book without an explicit structure and a scene without a known arc track the inferred protagonist, as before arcs.
"""
from ..book.structure import arc_order


def has_explicit_protagonists(story) -> bool:
    structure = getattr(story, 'book_structure', None)
    return bool(structure) and any(arc.protagonist_id for part in structure.parts for arc in part.arcs)


def arcs_of(story, scene) -> list[str]:
    """Arcs of the scene from the explicit structure: zero or one for now, a list once meeting scenes exist."""
    structure = getattr(story, 'book_structure', None)
    if structure is None or getattr(scene, 'trashed_at', None):
        return []  # the trash keeps the binding, but a trashed scene tracks the inferred protagonist
    arc = story.scene_arcs.get(scene.id)
    return [arc] if arc in arc_order(structure) else []


def scene_tracked(story, cards, scenes, scene) -> list[str]:
    from ..memory.core import tracked_characters
    inferred = tracked_characters(cards, scenes)
    arcs = arcs_of(story, scene)
    if not arcs:
        return inferred
    protagonists = {arc.id: arc.protagonist_id for part in story.book_structure.parts for arc in part.arcs}
    known = {card.id for card in cards}
    result = []
    for arc in arcs:
        explicit = protagonists.get(arc)
        for character in ([explicit] if explicit in known else inferred):
            if character not in result:
                result.append(character)
    return result


def scene_hero(story, cards, scenes, scene) -> str | None:
    """The acquaintance hero of a scene: the first of its tracked characters; None without cards."""
    tracked = scene_tracked(story, cards, scenes, scene) if cards else []
    return tracked[0] if tracked else None
