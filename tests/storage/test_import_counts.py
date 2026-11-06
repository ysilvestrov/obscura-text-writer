import json
import sqlite3

import pytest

from storygen.authoring.imports import SourceFile, import_sources, ImportBatchFailure, ImportBatchConflict
from storygen.domain import StoryCreate
from storygen.storage.repository import Repository


def upload(repo, story_id, text, kind):
    result = import_sources(repo, story_id, [SourceFile(name='synthetic.md', raw=text.encode(), kind=kind)])
    return next(row for row in repo.list_source_files(story_id) if row['id'] == result.files[0].source_id)


def test_counts_persist_new_materials_not_duplicates_or_current_totals(tmp_path):
    repo = Repository(tmp_path); story = repo.create_story(StoryCreate(title='Synthetic'))
    one = upload(repo, story.id, '## Анна\nЧитає.', 'source_characters')
    two = upload(repo, story.id, '## Анна\nДубль.\n## Марія\nПише.', 'source_characters')
    zero = upload(repo, story.id, '## Анна\nДубль.', 'source_characters')
    plan = upload(repo, story.id, 'Сцена 2: День\nПодія.', 'source_plan')
    mixed = upload(repo, story.id, 'Сцена 2: Дубль\nПропуск.\nСцена 3: Нова\nПодія.\n## Інтерлюдія\nТиша.', 'source_plan')
    assert [(r['created_scene_count'], r['created_character_count']) for r in [one,two,zero,plan,mixed]] == [(0,1),(0,1),(0,0),(1,0),(2,0)]
    stored = {r['id']: r for r in Repository(tmp_path).list_source_files(story.id)}
    assert stored[one['id']]['created_character_count'] == 1
    assert stored[mixed['id']]['created_scene_count'] == 2


def test_counter_metadata_is_derived_atomically_and_legacy_stays_unknown(tmp_path, monkeypatch):
    repo = Repository(tmp_path); story = repo.create_story(StoryCreate(title='Synthetic'))
    original = repo.publish_import
    def forged(story_id, revision, publication):
        publication.metadata.update(created_scene_count=999, created_character_count=999)
        return original(story_id, revision, publication)
    monkeypatch.setattr(repo, 'publish_import', forged)
    row = upload(repo, story.id, 'Сцена 1: День\nПодія.', 'source_plan')
    assert (row['created_scene_count'], row['created_character_count']) == (1,0)
    with repo.db.connection() as db:
        raw = json.loads(db.execute('SELECT payload FROM source_files WHERE id=?',(row['id'],)).fetchone()[0])
        raw.pop('created_scene_count'); raw.pop('created_character_count')
        db.execute('UPDATE source_files SET payload=? WHERE id=?',(json.dumps(raw),row['id']))
    legacy = repo.list_source_files(story.id)[0]
    assert legacy.get('created_scene_count') is None and legacy.get('created_character_count') is None


def test_failed_publication_never_leaves_counts_or_source_record(tmp_path, monkeypatch):
    repo = Repository(tmp_path); story = repo.create_story(StoryCreate(title='Synthetic'))
    calls=[]
    def fail(*_):
        calls.append('touch')
        raise sqlite3.OperationalError('Synthetic rollback')
    monkeypatch.setattr(repo, '_touch_story', fail)
    with pytest.raises(ImportBatchFailure,match="Імпорт не застосовано"):
        upload(repo, story.id, 'Сцена 1: День\nПодія.', 'source_plan')
    assert calls==['touch']
    assert repo.list_source_files(story.id) == []
    assert repo.list_scenes(story.id) == []


def test_stale_revision_never_publishes_source_or_counts(tmp_path,monkeypatch):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Synthetic'))
    original=repo.publish_import
    def stale(story_id,revision,publication):
        return original(story_id,revision-1,publication)
    monkeypatch.setattr(repo,'publish_import',stale)
    with pytest.raises(ImportBatchConflict,match='Матеріали вже змінено'):
        upload(repo,story.id,'Сцена 1: День\nПодія.','source_plan')
    assert repo.list_source_files(story.id)==[]
    assert repo.list_scenes(story.id)==[]
    assert repo.get_story(story.id).characters_version_id is None
