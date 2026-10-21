from ..domain import Scene, VersionRef


def invalidate_dependents(repo,changed_version_ids: list[str]) -> list[str]:
    return repo.invalidate_dependents(changed_version_ids)


def select_prose(repo,scene_id: str,version_id: str,expected_revision: int) -> Scene:
    return repo.set_head(scene_id,'prose',version_id,expected_revision)


def save_manual_prose(repo,scene_id: str,text: str,expected_revision: int) -> VersionRef:
    if not text.strip():
        raise ValueError('Проза не може бути порожньою')
    scene=repo.get_scene(scene_id)
    ref=repo.save_version(scene.story_id,scene.id,'manual',text,[])
    repo.set_head(scene.id,'prose',ref.id,expected_revision)
    return ref


def save_manual_draft(repo,scene_id: str,text: str,expected_revision: int) -> VersionRef:
    if not text.strip():
        raise ValueError('Чернетка не може бути порожньою')
    scene=repo.get_scene(scene_id)
    ref=repo.save_version(scene.story_id,scene.id,'draft',text,[])
    repo.set_head(scene.id,'draft',ref.id,expected_revision)
    return ref
