"""MEMORY-MERGE: the memory a scene extends — the only place that names it.

A scene with one head extends the selected memory of that head (the last ancestor in reading order); a scene whose
lineage needs a merge extends the usable `memory_merge` version of its merge point, and without one its context is not
built. Callers never read `previous[-1].heads['memory']` themselves (guard test)."""
import json
from dataclasses import dataclass, field

MERGE_REQUIRED = 'Потрібне злиття пам’яті перед цією сценою'


class MergeRequired(ValueError):
    def __init__(self, merge_key: str):
        super().__init__(MERGE_REQUIRED)
        self.merge_key = merge_key


@dataclass(frozen=True)
class PreviousMemory:
    memory_id: str | None
    merge_key: str | None = None
    ancestors: list = field(default_factory=list)
    series_start: bool = False  # SERIES: memory_id is the book's start snapshot (scene 0)


def _peek_view(view):
    """A read-only facade for selector evaluation: no freshness recomputation, no recorded dependencies."""
    class Peek:
        def get_version(self, id):
            return view.peek_version(id)

        def read_text(self, id):
            ref = view.peek_version(id)
            return view.read_blob(ref.relative_path, ref.sha256).decode('utf-8')
    return Peek() if hasattr(view, 'peek_version') else view


def previous_memory(view, scene, *, peek: bool = False, require: bool = True) -> PreviousMemory:
    from ..book.lineage import lineage_map, previous_scenes
    story = (view.peek_story if peek and hasattr(view, 'peek_story') else view.get_story)(scene.story_id)
    scenes = (view.peek_scenes if peek and hasattr(view, 'peek_scenes') else view.list_scenes)(scene.story_id)
    ancestors = previous_scenes(story, scenes, scene)
    if not ancestors:
        if story.series_start_version_id:
            return PreviousMemory(story.series_start_version_id, None, [], True)
        return PreviousMemory(None, None, [])
    item = lineage_map(story, scenes).get(scene.id)
    if item is None or not item.needs_merge:
        return PreviousMemory(ancestors[-1].heads.get('memory'), None, ancestors)
    from ..storage.memory_merges import merge_point, usable_merge
    point = merge_point(story, scenes, scene_id=scene.id)
    version_id = usable_merge(_peek_view(view) if peek else view, story, scenes, point)
    if version_id is None and require:
        raise MergeRequired(point.key)
    return PreviousMemory(version_id, point.key, ancestors)


def read_previous_journal(view, previous: PreviousMemory, *, peek: bool = False):
    """The journal of `previous` (a scene memory or the journal inside a merge); ValueError/KeyError/OSError propagate."""
    from .journal import MemoryJournal, load_memory
    reader = _peek_view(view) if peek else view
    raw = reader.read_text(previous.memory_id)
    if previous.series_start:
        from .series_start import read_series_start
        return read_series_start(raw, previous.memory_id).journal
    if previous.merge_key:
        return MemoryJournal.model_validate(json.loads(raw)['journal'])
    return load_memory(raw)
