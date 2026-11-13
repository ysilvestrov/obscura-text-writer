"""Story time of a book's arcs (STORY-TIME): where an arc starts in story time; pure, no IO."""
from ..memory.story_time import Moment, is_flashback, scene_moment
from .structure import effective_structure

__all__ = ['arc_start', 'is_flashback']


def arc_start(story, scenes, arc_id: str) -> Moment | None:
    """The moment of the arc's first active scene in reading order that is not a flashback; None when the arc has no
    such scene or that scene has no time mark."""
    active = sorted((s for s in scenes if not s.trashed_at), key=lambda s: s.position)
    arcs_of = effective_structure(story, active).arcs_of
    for scene in active:
        if arc_id in arcs_of.get(scene.id, ()) and not is_flashback(scene):
            return scene_moment(scene.beats)
    return None
