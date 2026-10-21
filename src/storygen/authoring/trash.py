def trash_story(repo, story_id, expected_revision):
    return repo.set_story_trashed(story_id, expected_revision, restore=False)


def restore_story(repo, story_id, expected_revision):
    return repo.set_story_trashed(story_id, expected_revision, restore=True)


def trash_scene(repo, story_id, scene_id, expected_revision):
    return repo.set_scene_trashed(story_id, scene_id, expected_revision, restore=False)


def restore_scene(repo, story_id, scene_id, expected_revision):
    return repo.set_scene_trashed(story_id, scene_id, expected_revision, restore=True)
