from ..domain import Scene, VersionRef


def invalidate_dependents(repo,changed_version_ids: list[str]) -> list[str]:
    return repo.invalidate_dependents(changed_version_ids)


def select_prose(repo,scene_id: str,version_id: str,expected_revision: int) -> Scene:
    return repo.set_head(scene_id,'prose',version_id,expected_revision)


def save_manual_prose(repo,scene_id: str,text: str,expected_revision: int) -> VersionRef:
    if not text.strip():
        raise ValueError('Проза не може бути порожньою')
    unchanged=repo.unchanged_scene_text(scene_id,'prose',text,expected_revision)
    if unchanged:return unchanged[1]
    scene=repo.get_scene(scene_id)
    from ..memory.forwarding import hidden_before
    policy=sorted(hidden_before(repo.context_view(scene.story_id),scene.id))
    ref=repo.save_version(scene.story_id,scene.id,'manual',text,[],manual_projection_policy=policy)
    repo.set_head(scene.id,'prose',ref.id,expected_revision)
    return ref


def save_manual_draft(repo,scene_id: str,text: str,expected_revision: int) -> VersionRef:
    if not text.strip():
        raise ValueError('Чернетка не може бути порожньою')
    unchanged=repo.unchanged_scene_text(scene_id,'draft',text,expected_revision)
    if unchanged:return unchanged[1]
    scene=repo.get_scene(scene_id)
    from ..memory.forwarding import hidden_before
    policy=sorted(hidden_before(repo.context_view(scene.story_id),scene.id))
    ref=repo.save_version(scene.story_id,scene.id,'draft',text,[],manual_projection_policy=policy)
    repo.set_head(scene.id,'draft',ref.id,expected_revision)
    return ref
