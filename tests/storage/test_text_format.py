import pytest

from storygen.domain import StoryCreate, SceneCreate, VersionRef
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_draft, save_manual_prose


@pytest.mark.parametrize('head,save', [('draft', save_manual_draft), ('prose', save_manual_prose)])
def test_format_is_explicit_and_legacy_clients_preserve_it(tmp_path, head, save):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Зорі'))
    scene = repo.create_scene(story.id, SceneCreate(title='Ранок', beats='Світло.'))
    first = save(repo, scene.id, '**літеральний** текст', scene.revision)
    assert first.content_format == 'plain'
    scene = repo.get_scene(scene.id)
    same = save(repo, scene.id, repo.read_text(first.id), scene.revision)
    assert same.id == first.id
    formatted = save(repo, scene.id, repo.read_text(first.id), scene.revision, content_format='markdown')
    assert formatted.id != first.id
    assert formatted.content_format == 'markdown'
    scene = repo.get_scene(scene.id)
    again = save(repo, scene.id, repo.read_text(formatted.id), scene.revision)
    assert again.id == formatted.id
    edited = save(repo, scene.id, '**інший** текст', scene.revision)
    assert edited.content_format == 'markdown'
    reopened = Repository(tmp_path)
    assert reopened.get_version(edited.id).content_format == 'markdown'
    payload = first.model_dump(); payload.pop('content_format')
    assert VersionRef.model_validate(payload).content_format == 'plain'


def test_format_restricted_to_prose_materials(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Зорі'))
    with pytest.raises(ValueError):
        repo.save_version(story.id, None, 'scene_plan', 'План', [], content_format='markdown')
    ref = repo.save_version(story.id, None, 'scene_plan', 'План', [])
    with pytest.raises(ValueError):
        VersionRef.model_validate({**ref.model_dump(), 'content_format': 'markdown'})
