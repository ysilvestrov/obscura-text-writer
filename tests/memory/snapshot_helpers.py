"""Test memory saved like the author's manual memory: a memory-scope snapshot of the current heads (VALID-LINKS Z3)."""
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.snapshots import build_dependency_snapshot


def memory_snapshot(repo, scene_id, refs):
    view = repo.context_view(repo.get_scene(scene_id).story_id)
    return build_dependency_snapshot(view, scene_id, 'memory', RoleSettings(provider=ProviderSettings(model='manual-memory')), list(refs))
