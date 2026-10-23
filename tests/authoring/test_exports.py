import json
import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.application.exports import export_story


def test_export_contains_selected_versions_in_scene_order(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='../Двері'))
    scenes=[repo.create_scene(story.id,SceneCreate(title=str(i))) for i in range(2)]
    for scene in scenes:save_manual_prose(repo,scene.id,'Текст '+str(scene.position),0)
    path=export_story(repo,story.id,'md')
    assert path.is_relative_to(tmp_path) and path.name.endswith('.md')
    assert path.read_text(encoding='utf-8').index('Текст 0')<path.read_text(encoding='utf-8').index('Текст 1')
    manifest=json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert len(manifest['scenes'])==2 and manifest['complete']


def test_export_blocks_partial_stale_or_missing_scene_by_default(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Твір'));repo.create_scene(story.id,SceneCreate(title='Без тексту'))
    with pytest.raises(ValueError):export_story(repo,story.id,'txt')
    path=export_story(repo,story.id,'txt',allow_incomplete=True)
    assert 'НЕЗАВЕРШЕНО' in path.read_text(encoding='utf-8')


@pytest.mark.parametrize('format', ['md', 'txt'])
@pytest.mark.parametrize('allow_incomplete', [False, True])
@pytest.mark.req('EXPORT-001')
def test_export_excludes_trashed_scene_from_text_and_manifest(tmp_path, format, allow_incomplete):
    from storygen.authoring.trash import trash_scene

    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    first = repo.create_scene(story.id, SceneCreate(title='Активна'))
    archived = repo.create_scene(story.id, SceneCreate(title='Архівна'))
    save_manual_prose(repo, first.id, 'Активний текст.', 0)
    save_manual_prose(repo, archived.id, 'Секрет архівної сцени.', 0)
    trash_scene(repo, story.id, archived.id, repo.get_scene(archived.id).revision)

    path = export_story(repo, story.id, format, allow_incomplete)
    text = path.read_text(encoding='utf-8')
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert 'Активний текст.' in text
    assert 'Архівна' not in text and 'Секрет' not in text
    assert [entry['scene_id'] for entry in manifest['scenes']] == [first.id]
    assert manifest['word_count'] == 2
    assert manifest['warnings'] == [] and manifest['complete'] is True


@pytest.mark.parametrize('format', ['md', 'txt'])
@pytest.mark.parametrize('allow_incomplete', [False, True])
def test_export_rejects_trashed_story_without_writing_files(tmp_path, format, allow_incomplete):
    from storygen.authoring.trash import trash_story

    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    save_manual_prose(repo, scene.id, 'Текст сцени.', 0)
    trash_story(repo, story.id, repo.get_story(story.id).revision)

    with pytest.raises(KeyError):
        export_story(repo, story.id, format, allow_incomplete)
    assert not (tmp_path / 'stories' / story.id / 'exports').exists()


def test_export_snapshot_keeps_one_sql_revision_during_concurrent_trash(tmp_path, monkeypatch):
    from storygen.authoring.trash import trash_scene

    repo = Repository(tmp_path)
    writer = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    ref = save_manual_prose(repo, scene.id, 'Початковий текст.', 0)
    expected_revision = repo.get_story(story.id).revision
    active_story = repo._active_story

    def read_then_trash(db, story_id):
        result = active_story(db, story_id)
        trash_scene(writer, story_id, scene.id, writer.get_scene(scene.id).revision)
        return result

    monkeypatch.setattr(repo, '_active_story', read_then_trash)
    captured_story, entries = repo.export_snapshot(story.id)
    assert captured_story.revision == expected_revision
    assert [(item.id, prose.id) for item, prose in entries] == [(scene.id, ref.id)]
    assert entries[0][0].trashed_at is None
    assert writer.list_scenes(story.id) == []


def test_export_uses_captured_head_when_prose_changes_after_snapshot(tmp_path, monkeypatch):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    original = save_manual_prose(repo, scene.id, 'Початковий текст.', 0)
    expected_revision = repo.get_story(story.id).revision
    read = repo.files.read
    replaced = False

    def read_then_replace(relative, sha256):
        nonlocal replaced
        data = read(relative, sha256)
        if not replaced:
            replaced = True
            save_manual_prose(repo, scene.id, 'Новіший текст.', repo.get_scene(scene.id).revision)
        return data

    monkeypatch.setattr(repo.files, 'read', read_then_replace)
    path = export_story(repo, story.id, 'md')
    manifest = json.loads(path.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    assert 'Початковий текст.' in path.read_text(encoding='utf-8')
    assert 'Новіший текст.' not in path.read_text(encoding='utf-8')
    assert manifest['revision'] == expected_revision
    assert manifest['scenes'][0]['version_id'] == original.id


def test_export_rejects_corrupt_prose_even_when_incomplete_allowed(tmp_path):
    from storygen.domain import StorageCorruption

    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена'))
    ref = save_manual_prose(repo, scene.id, 'Початковий текст.', 0)
    repo.files.resolve(ref.relative_path).write_text('Пошкоджено.', encoding='utf-8')
    with pytest.raises(StorageCorruption):
        export_story(repo, story.id, 'md', allow_incomplete=True)
