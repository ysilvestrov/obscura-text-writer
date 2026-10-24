from ..domain import Scene, Story
from ..storage.repository import Repository


def rename_story(repo: Repository,story_id: str,title: str,expected_revision: int) -> Story:
    return repo.rename_story(story_id,title,expected_revision)


def update_scene_plan(repo: Repository, scene_id: str, text: str, expected_revision: int) -> Scene:
    return repo.update_scene_plan(scene_id, text, expected_revision)


def update_scene(repo: Repository, scene_id: str, changes: dict, expected_revision: int) -> Scene:
    return repo.update_scene_metadata(scene_id, changes, expected_revision)


def reorder_scenes(repo: Repository, story_id: str, scene_ids: list[str], expected_revision: int) -> Story:
    return repo.reorder_scenes(story_id, scene_ids, expected_revision)
