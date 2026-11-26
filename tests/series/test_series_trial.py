"""R-47 (LONG-PROSE-TRIAL): a trial series holds two given books plus its bible, for good."""
import pytest

from storygen import build_edition
from storygen.book.guard import (NO_LONG_PROSE, READ_ONLY, READ_ONLY_SERIES, TRIAL_BOOK_ALONE, TRIAL_SERIES_FULL,
                                 TRIAL_USED)
from storygen.domain import StoryCreate
from storygen.storage import series as store
from storygen.storage.long_prose_trial import trial
from tests.web.test_long_prose_guard import setup
from tests.web.test_long_prose_trial_api import detail, structure_put, structured_book


def trial_series(client, title='Сага'):
    response = client.post('/api/series', json={'title': title, 'trial': True})
    assert response.status_code == 200, response.text
    return response.json()['id']


def new_book(client, series_id, title):
    return client.post(f'/api/series/{series_id}/books', json={'title': title})


def move(client, repo, story_id, series_id, number):
    story = repo.get_story(story_id)
    return client.patch(f'/api/stories/{story_id}/series',
                        json={'series_id': series_id, 'number': number, 'expected_revision': story.revision})


def rename(client, repo, story_id):
    return client.patch(f'/api/stories/{story_id}', json={'title': 'Х', 'expected_revision': repo.get_story(story_id).revision})


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_series_is_created_with_the_trial_only(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    refused = client.post('/api/series', json={'title': 'Без проби'})
    assert refused.status_code == 400 and NO_LONG_PROSE in detail(refused)
    series_id = trial_series(client)
    assert trial(repo).kind == 'series' and trial(repo).id == series_id
    again = client.post('/api/series', json={'title': 'Друга', 'trial': True})
    assert again.status_code == 400 and TRIAL_USED in detail(again)
    assert [item.title for item in store.list_series(repo)] == ['Сага']
    assert client.get('/series').status_code == 200 and client.get(f'/series/{series_id}').status_code == 200


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_series_page_is_open_while_the_trial_is_free(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    assert client.get('/series').status_code == 200
    client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True})
    assert client.get('/series').status_code == 404


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_two_new_books_then_the_third_is_refused(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    series_id = trial_series(client)
    first, second = (new_book(client, series_id, t).json()['id'] for t in ('Перша', 'Друга'))
    assert trial(repo).books == [first, second]
    assert rename(client, repo, second).status_code == 200
    count = len(repo.list_stories(include_trashed=True))
    third = new_book(client, series_id, 'Третя')
    assert third.status_code == 400 and TRIAL_SERIES_FULL in detail(third)
    assert len(repo.list_stories(include_trashed=True)) == count


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_structured_book_moves_into_the_trial_series_only(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    other_series = store.create_series(repo, 'Чужа')
    series_id = trial_series(client)
    new_book(client, series_id, 'Перша')
    refused = move(client, repo, story.id, other_series.id, 1)
    assert refused.status_code == 400 and READ_ONLY in detail(refused)
    assert move(client, repo, story.id, series_id, 2).status_code == 200
    assert story.id in trial(repo).books
    assert structure_put(client, repo.get_story(story.id)).status_code == 200


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_a_book_that_left_keeps_its_place_and_its_parts(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    series_id = trial_series(client)
    new_book(client, series_id, 'Перша')
    move(client, repo, story.id, series_id, 2)
    left = move(client, repo, story.id, None, None)
    assert left.status_code == 200, left.text
    assert structure_put(client, repo.get_story(story.id)).status_code == 200
    third = new_book(client, series_id, 'Третя')
    assert third.status_code == 400 and TRIAL_SERIES_FULL in detail(third)
    assert move(client, repo, story.id, series_id, 2).status_code == 200
    assert len(trial(repo).books) == 2


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_book_added_in_another_edition_is_read_only_in_store(tmp_path, store_edition, monkeypatch):
    client, app, repo, story, scene = setup(tmp_path)
    series_id = trial_series(client)
    first = new_book(client, series_id, 'Перша').json()['id']
    monkeypatch.setattr(build_edition, 'current', lambda: build_edition.BuildEdition())
    second = store.create_book(repo, series_id, 'Друга')
    third = store.create_book(repo, series_id, 'Третя')
    monkeypatch.setattr(build_edition, 'current', lambda: store_edition)
    assert trial(repo).books == [first]
    refused = rename(client, repo, third.id)
    assert refused.status_code == 400 and READ_ONLY_SERIES in detail(refused)
    assert rename(client, repo, first).status_code == 200
    assert second.id not in trial(repo).books


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_bible_of_the_trial_series_is_free_and_editable(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    series_id = trial_series(client)
    response = client.post(f'/api/series/{series_id}/bible', json={'title': 'Світ'})
    assert response.status_code == 200, response.text
    assert trial(repo).books == []
    assert rename(client, repo, response.json()['id']).status_code == 200


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_book_does_not_join_a_series(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True})
    saga = store.create_series(repo, 'Сага')
    response = move(client, repo, story.id, saga.id, 1)
    assert response.status_code == 400 and TRIAL_BOOK_ALONE in detail(response)


def make_bible(client, repo, story_id, series_id):
    story = repo.get_story(story_id)
    return client.patch(f'/api/stories/{story_id}/series',
                        json={'series_id': series_id, 'bible': True, 'expected_revision': story.revision})


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_bible_place_is_one_and_cannot_rotate_books(tmp_path, store_edition):
    """Final review C1: the bible of the trial series is remembered like its books, so it is no rotation slot."""
    from storygen.book.guard import TRIAL_BIBLE_USED
    client, app, repo, story, scene = setup(tmp_path)
    series_id = trial_series(client)
    new_book(client, series_id, 'Перша')
    new_book(client, series_id, 'Друга')
    assert make_bible(client, repo, story.id, series_id).status_code == 200
    assert trial(repo).bible == story.id
    assert move(client, repo, story.id, None, None).status_code == 200
    assert structure_put(client, repo.get_story(story.id)).status_code == 200  # the remembered bible keeps long prose
    other = structured_book(repo, 'Інша')
    refused = make_bible(client, repo, other.id, series_id)
    assert refused.status_code == 400 and TRIAL_BIBLE_USED in detail(refused)
    assert structure_put(client, repo.get_story(other.id)).status_code == 400


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_book_of_the_trial_series_does_not_carry_it_to_another_series(tmp_path, store_edition, monkeypatch):
    """Final review I1: a listed book may leave the trial series only to stand alone."""
    client, app, repo, story, scene = setup(tmp_path)
    series_id = trial_series(client)
    move(client, repo, story.id, series_id, 1)
    monkeypatch.setattr(build_edition, 'current', lambda: build_edition.BuildEdition())
    other = store.create_series(repo, 'Чужа')
    monkeypatch.setattr(build_edition, 'current', lambda: store_edition)
    refused = move(client, repo, story.id, other.id, 1)
    assert refused.status_code == 400 and TRIAL_BOOK_ALONE in detail(refused)
    refused = make_bible(client, repo, story.id, other.id)
    assert refused.status_code == 400 and TRIAL_BOOK_ALONE in detail(refused)


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_book_does_not_become_a_bible_of_another_series(tmp_path, store_edition):
    """Final review I2."""
    client, app, repo, story, scene = setup(tmp_path)
    client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True})
    saga = store.create_series(repo, 'Сага')
    response = make_bible(client, repo, story.id, saga.id)
    assert response.status_code == 400 and TRIAL_BOOK_ALONE in detail(response)


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_existing_bible_is_remembered_at_claim(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    item = store.create_series(repo, 'Сага')
    bible = store.create_bible(repo, item.id, 'Світ')
    assert client.post('/api/long-prose-trial', json={'series_id': item.id, 'confirm': True}).status_code == 200
    assert trial(repo).bible == bible.id and trial(repo).books == []
