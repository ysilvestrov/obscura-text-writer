"""SERIES-S02/S03: the summary of a book and the start snapshot of the next one (neutral examples)."""
import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.series import SUMMARY_NEEDS_MERGE, SUMMARY_NO_MEMORY, book_summary, source_book
from storygen.characters.models import load_characters
from storygen.domain import SceneCreate
from storygen.memory.series_start import read_series_start
from storygen.storage import series as store
from storygen.storage.integrity import check_integrity
from storygen.storage.repository import Repository
from storygen.web.app import create_app
from tests.series.helpers import book, card, finished_book, into_series, publish_cards


def series_with_book_1(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Серія')
    first, scenes, cloth = finished_book(repo)
    into_series(repo, first, item.id, 1)
    return repo, item, repo.get_story(first.id), scenes, cloth


def test_source_is_nearest_previous_not_in_trash(tmp_path):
    repo, item, first, scenes, cloth = series_with_book_1(tmp_path)
    second, _ = book(repo, 'Книга 2')
    second = into_series(repo, second, item.id, 2)
    third, _ = book(repo, 'Книга 3')
    third = into_series(repo, third, item.id, 3)
    assert source_book(repo.list_stories(), repo.get_story(third.id)).id == second.id
    repo.set_story_trashed(second.id, repo.get_story(second.id).revision, False)
    assert source_book(repo.list_stories(include_trashed=True), repo.get_story(third.id)).id == first.id
    assert source_book(repo.list_stories(), first) is None


def test_no_snapshot_without_a_summary_and_no_skip(tmp_path):
    repo, item, first, scenes, cloth = series_with_book_1(tmp_path)
    second, _ = book(repo, 'Книга 2')
    second = into_series(repo, second, item.id, 2)
    assert second.series_start_version_id is not None
    third, _ = book(repo, 'Книга 3')
    third = into_series(repo, third, item.id, 3)
    assert third.series_start_version_id is None
    with pytest.raises(ValueError, match=store.NO_SOURCE):
        store.take_snapshot(repo, third.id, third.revision)


def test_unfinished_book_has_no_summary(tmp_path):
    repo, item, first, scenes, cloth = series_with_book_1(tmp_path)
    assert book_summary(repo.context_view(first.id), first)[1] is None
    repo.create_scene(first.id, SceneCreate(title='Сцена 3', beats='Ще не написано.'))
    assert book_summary(repo.context_view(first.id), repo.get_story(first.id)) == (None, SUMMARY_NO_MEMORY)


def test_book_with_arcs_ending_in_two_arcs_needs_the_book_end_merge(tmp_path):
    from tests.memory.merge_helpers import arc_book
    repo, story, scenes = arc_book(tmp_path, 'A B A B', [['A', 'B']])
    assert book_summary(repo.context_view(story.id), repo.get_story(story.id)) == (None, SUMMARY_NEEDS_MERGE)


def test_entering_the_series_takes_the_snapshot(tmp_path):
    repo, item, first, scenes, cloth = series_with_book_1(tmp_path)
    second, _ = book(repo, 'Книга 2')
    second = into_series(repo, second, item.id, 2)
    data = read_series_start(repo.read_text(second.series_start_version_id), second.series_start_version_id)
    assert cloth.claim_id in {e.claim_id for e in data.journal.events}
    assert data.source['source_story_id'] == first.id
    assert data.source['source_summary_version_id'] == scenes[1].heads['memory']
    cards = load_characters(repo.read_text(second.characters_version_id))
    assert [(c.id, c.name) for c in cards] == [('A', 'Анна')]
    entry = cards[0].entries[0]
    assert (entry.id, entry.availability, entry.available_from_scene_id) == ('e1', 'timeless', None)
    assert repo.get_version(entry.sources[0].version_id).story_id == second.id
    assert set(data.source['source_card_hashes']) == {'A'}
    assert check_integrity(repo.root).ok, check_integrity(repo.root).issues


def test_card_name_clash_refuses(tmp_path):
    repo, item, first, scenes, cloth = series_with_book_1(tmp_path)
    second, _ = book(repo, 'Книга 2')
    publish_cards(repo, second, [card('own', ' анна ')])
    second = into_series(repo, second, item.id, 2)
    assert second.series_start_version_id is None
    with pytest.raises(ValueError, match='Анна'):
        store.take_snapshot(repo, second.id, second.revision)


def test_finishing_the_source_later_takes_no_snapshot(tmp_path):
    repo, item, first, scenes, cloth = series_with_book_1(tmp_path)
    extra = repo.create_scene(first.id, SceneCreate(title='Сцена 3', beats='Пізніше.'))
    second, scene = book(repo, 'Книга 2')
    second = into_series(repo, second, item.id, 2)
    assert second.series_start_version_id is None
    repo.set_scene_trashed(first.id, extra.id, repo.get_scene(extra.id).revision, False)
    assert book_summary(repo.context_view(first.id), repo.get_story(first.id))[1] is None
    assert repo.get_story(second.id).series_start_version_id is None
    assert not repo.get_version(repo.get_scene(scene.id).heads['prose']).stale


def test_new_book_button_takes_the_snapshot(tmp_path):
    repo, item, first, scenes, cloth = series_with_book_1(tmp_path)
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        response = client.post(f'/api/series/{item.id}/books', json={'title': 'Книга 2'})
        assert response.status_code == 200, response.text
        created = response.json()
    assert created['series_number'] == 2 and created['series_start_version_id']
