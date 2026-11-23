"""MEMORY-CARRY: the mechanical carry of a new scene memory into the journals of later scenes.

A carried journal is the new journal of the previous memory plus the scene's own source and own events, unchanged, so
its memory_digest (and every fingerprint after it) stays. The carry state of a scene is derived, never stored: its
inherited journal part against the journal of its current previous memory, read only relative to recorded carry runs
(Ruling of R-44 PR 2b Task 3: legacy journals that diverged before any carry are not marked)."""
from typing import Literal

from .journal import MemoryJournal, _extend, validate_memory_journal

CARRY_PENDING = 'Пам’ять переноситься: модельні етапи цієї сцени стануть доступні, коли перенос пам’яті дійде до неї'
CARRY_MISSING = 'Записи сцени посилаються на твердження, яких немає в новій пам’яті попередньої сцени'
ACTIVE = frozenset({'queued', 'running', 'pause_requested', 'cancellation_requested'})
STALLED = frozenset({'paused', 'failed', 'interrupted'})
MAX_CHAIN = 200
CarryState = Literal['current', 'pending', 'failed']


class CarryFailed(ValueError):
    """The scene's own events do not apply to the new journal of its previous memory."""


def own_source(journal: MemoryJournal) -> str | None:
    return journal.source_prose_ids[-1] if journal.source_prose_ids else None


def same_inheritance(previous: MemoryJournal, journal: MemoryJournal) -> bool:
    """The journal extends exactly `previous`: its sources before its own and its events of earlier sources."""
    own = own_source(journal)
    return (journal.source_prose_ids[:-1] == previous.source_prose_ids
            and [event for event in journal.events if event.source_version_id != own] == previous.events)


def carry_journal(previous: MemoryJournal, journal: MemoryJournal, sources: dict | None = None) -> MemoryJournal:
    """`previous` + the scene's own source + its own events unchanged; CarryFailed when an own event names a claim the
    new previous journal does not have, or (with `sources`, id -> text) the carried journal does not validate."""
    own = own_source(journal)
    if own is None:
        raise CarryFailed('Пам’ять сцени не має власного джерела')
    events = [event for event in journal.events if event.source_version_id == own]
    known = {event.claim_id for event in previous.events}
    for event in events:
        if event.resolves_claim_id is not None and event.resolves_claim_id not in known:
            raise CarryFailed(CARRY_MISSING)
        if event.operation == 'add':
            known.add(event.claim_id)
        elif event.claim_id not in known:
            raise CarryFailed(CARRY_MISSING)
    try:
        carried = _extend(previous, own, [event.model_copy(deep=True) for event in events],
                          max(previous.schema_version, journal.schema_version))
        if sources is not None:
            validate_memory_journal(carried, sources)
    except (ValueError, KeyError) as exc:
        raise CarryFailed(str(exc)) from None
    return carried


def _predecessor(before):
    """The scene whose memory a scene extends directly; None for a merge, a series start or a first scene."""
    return before.ancestors[-1].id if before.ancestors and not before.merge_key else None


def _differs(view, reader, scene, before):
    """True/False: the scene's journal does/does not extend the journal of its current previous memory; None when
    there is nothing to compare (no previous memory) or a journal is unreadable."""
    from ..storage.context_view import memo
    from .journal import load_memory
    from .previous import read_previous_journal
    memory_id = scene.heads.get('memory')
    if not memory_id or before.memory_id is None:
        return None
    try:
        journal = memo(reader, ('memory', memory_id, 'scene'), lambda: load_memory(reader.read_text(memory_id)))
        previous = read_previous_journal(view, before, peek=True)
    except (ValueError, KeyError, OSError):
        return None
    return not same_inheritance(previous, journal)


def _compute(view) -> dict:
    from .previous import _peek_view, previous_memory
    runs = getattr(view, 'memory_carries', None) or []
    remaining, failures = set(), set()
    for index, run in enumerate(runs):
        # A paused, failed or interrupted carry still covers its remaining scenes until a later carry run replaces it.
        if run.state in ACTIVE or (run.state in STALLED and index == len(runs) - 1):
            remaining.update(task.get('scene_id') for task in run.tasks[run.cursor:])
        checkpoint = run.checkpoint or {}
        if checkpoint.get('failed_scene_id'):
            failures.add((checkpoint['failed_scene_id'], checkpoint.get('memory_id')))
    failed_scenes = {scene_id for scene_id, _ in failures}
    if not remaining and not failures:
        return {}
    reader = _peek_view(view)
    states = {}
    for scene in sorted((s for s in view.scenes.values() if not s.trashed_at), key=lambda s: (s.position, s.id)):
        if (scene.id not in remaining and scene.id not in failed_scenes) or not scene.heads.get('memory'):
            continue
        before = previous_memory(view, scene, peek=True, require=False)
        differs = _differs(view, reader, scene, before)
        if scene.id in remaining and (differs or states.get(_predecessor(before)) == 'pending'):
            states[scene.id] = 'pending'
        elif differs is False:
            states[scene.id] = 'current'
        elif differs and (scene.id, scene.heads['memory']) in failures:
            states[scene.id] = 'failed'
    return states


def carry_states(view) -> dict:
    """{scene_id: state} for the scenes a carry run covers or stopped at; a scene outside carry runs is absent."""
    from ..storage.context_view import memo
    return memo(view, ('carry_states',), lambda: _compute(view))


def carry_state(view, scene_id: str) -> CarryState | None:
    """`pending` while an active carry run has not passed the scene and there is something to carry (or its previous
    scene is pending), `failed` when a finished run could not carry the scene's current memory and it still differs,
    `current` when its journal extends the current previous journal; None when there is nothing to compare or the
    journal diverged without a carry run (legacy, not marked)."""
    states = carry_states(view)
    if scene_id in states:
        return states[scene_id]
    scene = view.scenes.get(scene_id)
    if scene is None or scene.trashed_at:
        return None
    from .previous import _peek_view, previous_memory
    differs = _differs(view, _peek_view(view), scene, previous_memory(view, scene, peek=True, require=False))
    return 'current' if differs is False else None


def carry_blocks(view, scene_id: str) -> bool:
    """Model stages of the scene wait: its memory, or the memory it extends, is still to be carried."""
    states = carry_states(view)
    if not states:
        return False
    if states.get(scene_id) == 'pending':
        return True
    scene = view.scenes.get(scene_id)
    if scene is None or scene.trashed_at:
        return False
    from .previous import previous_memory
    return states.get(_predecessor(previous_memory(view, scene, peek=True, require=False))) == 'pending'


def require_not_carrying(repo, scene_id: str) -> None:
    """MCP-BRIDGE: a chat stage result or chat draft waits for the carry like a model stage (409)."""
    from ..domain import RevisionConflict
    scene = repo.get_scene(scene_id)
    if carry_blocks(repo.context_view(scene.story_id), scene_id):
        raise RevisionConflict(CARRY_PENDING)


def carried_to(view, old_id: str | None, new_id: str | None) -> bool:
    """`new_id` carries `old_id` (directly or through a chain of carries)."""
    if not old_id or not new_id or old_id == new_id:
        return False
    ref = view.versions.get(new_id)
    for _ in range(MAX_CHAIN):
        if ref is None or not ref.memory_carry_of:
            return False
        if ref.memory_carry_of == old_id:
            return True
        ref = view.versions.get(ref.memory_carry_of)
    return False


def carry_successor(view, memory_id: str) -> str | None:
    """The current memory head of the memory's scene when it carries this memory."""
    ref = view.versions.get(memory_id)
    scene = view.scenes.get(ref.scene_id) if ref is not None and ref.kind == 'memory' and ref.scene_id else None
    head = scene.heads.get('memory') if scene is not None and not scene.trashed_at else None
    return head if carried_to(view, memory_id, head) else None
