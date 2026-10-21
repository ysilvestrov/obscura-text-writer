import pytest

from storygen.domain import RevisionConflict, StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.providers.models import ProviderSettings, RoleSettings


def test_shared_roles_rollback_if_one_prompt_is_foreign(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Перший'))
    other = repo.create_story(StoryCreate(title='Другий'))
    prompt = repo.save_version(other.id, None, 'prompt', 'Чужий промпт', [])
    settings = RoleSettings(provider=ProviderSettings(model='test'))
    updates = {'editor': settings.model_dump(), 'writer': settings.model_copy(update={'prompt_version_id': prompt.id}).model_dump()}
    with pytest.raises(ValueError):
        repo.write_role_settings(story.id, updates, story.revision)
    assert repo.read_role_settings(story.id) == {}
    assert repo.get_story(story.id).revision == story.revision


def test_blueprint_conflict_keeps_heads_and_scene_order(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Проєкт'))
    scene = repo.create_scene(story.id, SceneCreate(title='Авторська сцена'))
    canon = repo.save_version(story.id, None, 'canon', 'Канон', [])
    cards = repo.save_version(story.id, None, 'character_cards', '[]', [])
    before = repo.get_story(story.id)
    with pytest.raises(RevisionConflict):
        repo.publish_blueprint(story.id, canon.id, cards.id, [], before.revision - 1)
    assert repo.get_story(story.id) == before
    assert [s.id for s in repo.list_scenes(story.id)] == [scene.id]


def test_restore_conflict_keeps_trash_state(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Кошик'))
    trashed = repo.set_story_trashed(story.id, story.revision, restore=False)
    with pytest.raises(RevisionConflict):
        repo.set_story_trashed(story.id, story.revision, restore=True)
    assert repo.get_story(story.id, include_trashed=True) == trashed
