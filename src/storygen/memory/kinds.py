"""Author memory-kind marks (#60, MEMORY-SELECT-S08): 'core' always shown, 'atmosphere' only within its quota.

Marks live in Story.memory_kind_overrides and act only when a request is built with selection; a request that fits
ignores them, and only a version built with selection records the selector scene/memory_kind_overrides."""
from ..memory.journal import load_memory

KINDS=('core','atmosphere')


def _journal(view,version_id):
    # Selector evaluation must not recompute freshness: peek and read the blob directly, as projection_policy does.
    try:
        ref=view.peek_version(version_id)
        return load_memory(view.read_blob(ref.relative_path,ref.sha256).decode('utf-8'))
    except (ValueError,KeyError,OSError):return None


def kind_overrides(view,scene_id) -> dict[str,str]:
    """Selector value scene/memory_kind_overrides: marks of the selection candidates in the memory before the scene."""
    scene=view.peek_scene(scene_id)
    marks=view.peek_story(scene.story_id).memory_kind_overrides
    if not marks:return {}
    from .previous import previous_memory, read_previous_journal
    before=previous_memory(view,scene,peek=True,require=False)
    try:journal=read_previous_journal(view,before,peek=True) if before.memory_id else None
    except (ValueError,KeyError,OSError):journal=None
    if journal is None:return {}
    from .projection import candidate_claim_ids
    try:candidates=candidate_claim_ids(journal)
    except ValueError:return {}
    return {cid:marks[cid] for cid in sorted(marks) if cid in candidates}


def tracked_ids(view,story,scene) -> set[str]:
    """BOOK-LINEAGE-S04: characters whose slots are core in this scene — the protagonists of its arcs."""
    from ..book.protagonists import scene_tracked
    from ..storage.snapshots import core_cards
    return set(scene_tracked(story,core_cards(view,story),view.peek_scenes(story.id),scene))


def tracked_anywhere(view,story) -> set[str]:
    """Characters whose slots are core in at least one active scene (a mark request without a scene)."""
    from ..book.protagonists import scene_tracked
    from ..storage.snapshots import core_cards
    cards,scenes=core_cards(view,story),view.peek_scenes(story.id)
    return {cid for scene in scenes if not scene.trashed_at for cid in scene_tracked(story,cards,scenes,scene)}


def is_core_slot(event,tracked) -> bool:
    """A slot of a tracked character is always in the core; a former protagonist's slot is an ordinary state."""
    return bool(event.slot and event.character_ids and event.character_ids[0] in tracked)


def find_claim(view,story_id,claim_id):
    """The latest event of the claim in the story's memory journals, newest scene first; None if absent."""
    for scene in sorted(view.peek_scenes(story_id),key=lambda s:s.position,reverse=True):
        memory_id=scene.heads.get('memory')
        journal=_journal(view,memory_id) if memory_id else None
        if journal is None:continue
        found=[e for e in journal.events if e.claim_id==claim_id]
        if found:return found[-1]
    return None
