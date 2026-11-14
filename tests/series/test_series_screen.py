"""SERIES-S07: the series screen API, the chronology axis and the series pages (neutral examples)."""
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.book.series import chronology
from storygen.domain import StoryCreate
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.web.app import create_app


def client_for(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    return TestClient(app, base_url='http://127.0.0.1'), app.state.repo


def book(repo, item, title, number, start=None):
    story = repo.create_story(StoryCreate(title=title))
    return store.set_story_series(repo, story.id, item.id, number, start, story.revision)


def test_chronology_starts_from_the_book_without_start(tmp_path):
    # The book without «Початок» is the origin; a start counts from its anchor, which must be an earlier book of the
    # series on the axis. A second book without start, a later or missing anchor and an anchor off the axis are outside.
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    first = book(repo, item, 'Перша', 1)
    prequel = book(repo, item, 'Передісторія', 2, SeriesStart(offset='Рік -10', anchor=1))
    later = book(repo, item, 'Пізніше', 3, SeriesStart(offset='Рік 2, День 5', anchor=1))
    chained = book(repo, item, 'Між ними', 4, SeriesStart(offset='Рік -1', anchor=3))
    second_origin = book(repo, item, 'Ще без початку', 5)
    forward = book(repo, item, 'Наперед', 6, SeriesStart(offset='Рік 1', anchor=7))
    off_axis = book(repo, item, 'Від неопори', 7, SeriesStart(offset='Рік 1', anchor=5))
    placed, outside = chronology(store.series_books(repo, item.id))
    assert placed == [prequel.id, first.id, chained.id, later.id]
    assert outside == [second_origin.id, forward.id, off_axis.id]


def test_chronology_keeps_release_order_outside_for_any_input_order(tmp_path):
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    first = book(repo, item, 'Перша', 1)
    second = book(repo, item, 'Друга', 2)
    third = book(repo, item, 'Третя', 3)
    assert chronology(list(reversed(store.series_books(repo, item.id)))) == ([first.id], [second.id, third.id])


def test_chronology_without_an_origin_places_nothing(tmp_path):
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    first = book(repo, item, 'Перша', 1, SeriesStart(offset='Рік 0', anchor=1))
    second = book(repo, item, 'Друга', 2, SeriesStart(offset='Рік 1', anchor=1))
    assert chronology(store.series_books(repo, item.id)) == ([], [first.id, second.id])


def test_series_api_lists_books_with_status_and_trash(tmp_path):
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    first = book(repo, item, 'Перша', 1)
    second = book(repo, item, 'Друга', 2)
    repo.set_story_trashed(second.id, second.revision, False)
    data = client.get(f'/api/series/{item.id}').json()
    assert data['series']['title'] == 'Сага'
    assert [(b['id'], b['number'], b['trashed']) for b in data['books']] == [(first.id, 1, False), (second.id, 2, True)]
    assert data['books'][0]['status']['state'] == 'first'
    assert data['placed'] == [first.id] and data['outside'] == [second.id]


def test_start_text_is_parsed_or_refused(tmp_path):
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    story = repo.create_story(StoryCreate(title='Книга'))
    response = client.patch(f'/api/stories/{story.id}/series', json={'series_id': item.id, 'number': 1,
                            'start_text': 'Рік -3 від шторму, опора 1', 'expected_revision': story.revision})
    assert response.status_code == 200, response.text
    assert response.json()['series_start'] == {'offset': 'Рік -3', 'anchor': 1}
    refused = client.patch(f'/api/stories/{story.id}/series', json={'series_id': item.id, 'number': 1,
                           'start_text': 'колись', 'expected_revision': response.json()['revision']})
    assert refused.status_code == 422


def test_series_pages(tmp_path):
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    assert client.get('/series').status_code == 200
    page = client.get(f'/series/{item.id}')
    assert page.status_code == 200 and 'series-page' in page.text
    assert 'href="/series"' in client.get('/').text


def test_series_pages_absent_in_store(tmp_path, store_edition):
    client, repo = client_for(tmp_path)
    assert client.get('/series').status_code == 404
    assert 'href="/series"' not in client.get('/').text


def test_a_book_with_a_negative_start_is_marked_as_a_prequel(tmp_path):
    # SERIES-S07: a prequel continues the previous book by release in 4a and carries a warning that prequels come in 4b.
    client, repo = client_for(tmp_path)
    item = store.create_series(repo, 'Сага')
    book(repo, item, 'Перша', 1, SeriesStart(offset='Рік 0', anchor=1))
    book(repo, item, 'Передісторія', 2, SeriesStart(offset='Рік -10, День 3', anchor=1))
    book(repo, item, 'Пізніше', 3, SeriesStart(offset='Рік 2', anchor=1))
    book(repo, item, 'Без початку', 4)
    data = client.get(f'/api/series/{item.id}').json()
    assert [b['status']['prequel'] for b in data['books']] == [False, True, False, False]
