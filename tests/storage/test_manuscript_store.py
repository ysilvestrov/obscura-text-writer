"""MANUSCRIPT-IMPORT: atomic creation of a new book from an imported manuscript (spec §4.3)."""
from datetime import datetime, timezone

import pytest

from storygen.domain import ManuscriptImportOrigin, StoryCreate
from storygen.storage.integrity import check_integrity
from storygen.storage.links import scene_links
from storygen.storage.manuscript_store import ManuscriptSceneData, publish_manuscript
from storygen.storage.repository import Repository

ORIGIN = ManuscriptImportOrigin(file_name='book.md', file_sha256='a' * 64, imported_at=datetime(2026, 11, 25, tzinfo=timezone.utc))
SCENES = [ManuscriptSceneData('Перша', 'Текст *перший*.', 'markdown', None, 2),
          ManuscriptSceneData('Друга', 'Текст другий.', 'markdown', None, 2),
          ManuscriptSceneData('Третя', 'Текст третій, трохи довший.', 'markdown', None, 4)]


def version_files(tmp_path):
    return [path for path in (tmp_path / 'data' / 'stories').rglob('*') if path.is_file()] \
        if (tmp_path / 'data' / 'stories').exists() else []


def test_publish_creates_story_scenes_and_manual_prose(tmp_path):
    repo = Repository(tmp_path / 'data')
    story, scenes = publish_manuscript(repo, StoryCreate(title='Книга'), SCENES, ORIGIN, False)
    stored = repo.list_scenes(story.id)
    assert [s.id for s in stored] == [s.id for s in scenes]
    assert [(s.title, s.position, s.target_words) for s in stored] == [('Перша', 0, 2), ('Друга', 1, 2), ('Третя', 2, 4)]
    view = repo.context_view(story.id)
    for scene, item in zip(stored, SCENES):
        version = view.get_version(scene.heads['prose'])
        assert (version.kind, version.complete, version.stale, version.content_format) == ('manual', True, False, 'markdown')
        assert version.manuscript_import == ORIGIN and version.dependency_snapshot.scope == 'author_text'
        assert repo.read_text(version.id) == item.text
        assert scene_links(view, scene.id)['memory'].status == 'unavailable'
    # Each later scene's snapshot names the prose heads of the scenes before it, as save_manual_prose would.
    last = view.get_version(stored[2].heads['prose']).dependency_snapshot
    assert {s.owner_id: s.expected for s in last.selectors if s.kind == 'head' and s.field == 'prose'} == \
        {stored[0].id: stored[0].heads['prose'], stored[1].id: stored[1].heads['prose']}
    assert repo.get_story(story.id).book_structure is None
    assert check_integrity(repo.root).ok


def test_publish_rolls_back_on_failure(tmp_path, monkeypatch):
    repo = Repository(tmp_path / 'data')
    original = Repository._insert_version_row
    calls = []

    def failing(self, db, version):
        calls.append(version.id)
        if len(calls) == 2:
            raise RuntimeError('збій запису версії')
        return original(self, db, version)
    monkeypatch.setattr(Repository, '_insert_version_row', failing)
    with pytest.raises(RuntimeError):
        publish_manuscript(repo, StoryCreate(title='Книга'), SCENES, ORIGIN, False)
    assert repo.list_stories(include_trashed=True) == []
    assert version_files(tmp_path) == []
    with repo.db.connection() as db:
        assert db.execute('SELECT COUNT(*) FROM scenes').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM versions').fetchone()[0] == 0


def test_parts_follow_part_index_not_title(tmp_path):
    repo = Repository(tmp_path / 'data')
    scenes = [ManuscriptSceneData('Перша', 'Один.', 'plain', 'Частина', 1, 0),
              ManuscriptSceneData('Друга', 'Два.', 'plain', 'Частина', 1, 1),
              ManuscriptSceneData('Третя', 'Три.', 'plain', 'Частина', 1, 1)]
    story, created = publish_manuscript(repo, StoryCreate(title='Книга'), scenes, ORIGIN, True)
    structure = repo.get_story(story.id).book_structure
    assert [part.title for part in structure.parts] == ['Частина', 'Частина']
    arcs = repo.get_story(story.id).scene_arcs
    assert arcs[created[1].id] == arcs[created[2].id] != arcs[created[0].id]
    view = repo.context_view(story.id)
    assert not any(view.get_version(view.get_scene(s.id).heads['prose']).stale for s in created)
    assert check_integrity(repo.root).ok


def test_series_slot_taken_rolls_back(tmp_path):
    from storygen.storage.series import create_book, create_series
    repo = Repository(tmp_path / 'data')
    series = create_series(repo, 'Серія')
    first = create_book(repo, series.id, 'Перша')
    before = len(version_files(tmp_path))
    with pytest.raises(ValueError):
        publish_manuscript(repo, StoryCreate(title='Книга'), SCENES, ORIGIN, False, series=(series.id, first.series_number))
    assert [s.id for s in repo.list_stories(include_trashed=True)] == [first.id]
    assert len(version_files(tmp_path)) == before


def test_publish_removes_files_when_write_fails(tmp_path, monkeypatch):
    repo = Repository(tmp_path / 'data')
    original = repo.files.write
    calls = []

    def failing(relative, content):
        calls.append(relative)
        if len(calls) == 3:
            raise OSError('диск повний')
        return original(relative, content)
    monkeypatch.setattr(repo.files, 'write', failing)
    with pytest.raises(OSError):
        publish_manuscript(repo, StoryCreate(title='Книга'), SCENES, ORIGIN, False)
    assert len(calls) == 3
    assert repo.list_stories(include_trashed=True) == []
    assert version_files(tmp_path) == []


def test_publish_lock_time_is_bounded(tmp_path):
    import time
    repo = Repository(tmp_path / 'data')
    scenes = [ManuscriptSceneData(f'Сцена {n}', 'Слово ' * 200, 'markdown', None, 200) for n in range(300)]
    started = time.perf_counter()
    story, created = publish_manuscript(repo, StoryCreate(title='Книга'), scenes, ORIGIN, False)
    elapsed = time.perf_counter() - started
    assert len(created) == 300
    assert elapsed < 3, elapsed  # other writers wait 5 s (busy_timeout) for the import's transaction
    view = repo.context_view(story.id)
    assert not view.get_version(created[-1].heads['prose']).stale
