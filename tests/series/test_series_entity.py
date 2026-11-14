"""SERIES-S01: the series entity and the series fields of a book (neutral examples)."""
import sqlite3

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import RevisionConflict, Story, StoryCreate
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.database import Database
from storygen.storage.repository import Repository
from storygen.web.app import create_app


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def test_create_rename_delete_with_cas(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Північний шлях')
    with pytest.raises(ValueError, match=store.SERIES_TITLE_TAKEN):
        store.create_series(repo, ' північний  шлях ')
    renamed = store.rename_series(repo, item.id, 'Південний шлях', item.revision)
    assert renamed.title == 'Південний шлях' and renamed.revision == item.revision + 1
    with pytest.raises(RevisionConflict):
        store.rename_series(repo, item.id, 'Інша', item.revision)
    assert [s.id for s in store.list_series(repo)] == [item.id]
    store.delete_series(repo, item.id, renamed.revision)
    assert store.list_series(repo) == []


def test_delete_refuses_a_series_with_a_trashed_book(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    book = repo.create_story(StoryCreate(title='Книга'))
    book = store.set_story_series(repo, book.id, item.id, 1, None, book.revision)
    repo.set_story_trashed(book.id, book.revision, False)
    with pytest.raises(ValueError, match=store.SERIES_NOT_EMPTY):
        store.delete_series(repo, item.id, store.get_series(repo, item.id).revision)


def test_number_unique_including_trash(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    first = repo.create_story(StoryCreate(title='Книга 1'))
    first = store.set_story_series(repo, first.id, item.id, 2, None, first.revision)
    repo.set_story_trashed(first.id, first.revision, False)
    second = repo.create_story(StoryCreate(title='Книга 2'))
    with pytest.raises(ValueError, match='Номер 2 у серії вже зайнятий'):
        store.set_story_series(repo, second.id, item.id, 2, None, second.revision)
    assert [b.id for b in store.series_books(repo, item.id)] == [first.id]


def test_series_and_number_go_together(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    book = repo.create_story(StoryCreate(title='Книга'))
    with pytest.raises(ValueError, match=store.SERIES_PAIR):
        store.set_story_series(repo, book.id, item.id, None, None, book.revision)
    book = store.set_story_series(repo, book.id, item.id, 1, SeriesStart(offset='Рік 2', anchor=1), book.revision)
    assert (book.series_id, book.series_number, book.series_start.anchor) == (item.id, 1, 1)
    left = store.set_story_series(repo, book.id, None, None, None, book.revision)
    assert (left.series_id, left.series_number, left.series_start, left.series_start_version_id) == (None, None, None, None)


def test_story_json_without_series_keys_reads_as_before():
    story = Story.model_validate({'id': 's1', 'title': 'Оповідання'})
    assert (story.series_id, story.series_number, story.series_start, story.series_start_version_id) == (None, None, None, None)


def test_series_over_http(tmp_path):
    with client_for(tmp_path) as client:
        created = client.post('/api/series', json={'title': 'Серія'})
        assert created.status_code == 200, created.text
        item = created.json()
        book = client.post('/api/stories', json={'title': 'Книга'}).json()
        patched = client.patch(f"/api/stories/{book['id']}/series", json={'series_id': item['id'], 'number': 1, 'expected_revision': book['revision']})
        assert patched.status_code == 200, patched.text
        assert client.patch(f"/api/series/{item['id']}", json={'title': 'Нова', 'expected_revision': item['revision']}).json()['title'] == 'Нова'
        assert client.delete(f"/api/series/{item['id']}?expected_revision=1").status_code == 400
        assert [s['id'] for s in client.get('/api/series').json()] == [item['id']]


def test_store_edition_refuses_series_edits(tmp_path, store_edition):
    with client_for(tmp_path) as client:
        refused = client.post('/api/series', json={'title': 'Серія'})
        assert refused.status_code == 400 and 'довгою прозою' in refused.text
        book = client.post('/api/stories', json={'title': 'Книга'}).json()
        assert client.patch(f"/api/stories/{book['id']}/series", json={'series_id': None, 'number': None, 'expected_revision': book['revision']}).status_code == 400


def test_migration_from_5_creates_the_table(tmp_path):
    path = tmp_path / 'db.sqlite'
    Database(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 6
        db.execute('DROP TABLE series')
        db.execute('PRAGMA user_version=5')
    Database(path)
    with sqlite3.connect(path) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 6
        assert db.execute("SELECT name FROM sqlite_master WHERE name='series'").fetchone()


def test_integrity_checks_series_references(tmp_path):
    from storygen.storage.integrity import check_integrity
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    book = repo.create_story(StoryCreate(title='Книга'))
    store.set_story_series(repo, book.id, item.id, 1, None, book.revision)
    assert check_integrity(repo.root).ok
    with repo.db.connection() as db:
        db.execute('DELETE FROM series')
    report = check_integrity(repo.root)
    assert [i.code for i in report.issues] == ['invalid_series']
