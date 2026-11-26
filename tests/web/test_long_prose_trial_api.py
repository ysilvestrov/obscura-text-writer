"""R-47 (LONG-PROSE-TRIAL): the author turns the one trial on for a book or a series."""
import pytest

from storygen.book.guard import NO_LONG_PROSE, READ_ONLY, TRIAL_CONFIRM, TRIAL_IN_SERIES, TRIAL_NOT_NEEDED, TRIAL_SERIES_FULL, TRIAL_USED
from storygen.domain import SceneCreate, StoryCreate
from storygen.storage import series as store
from storygen.storage.book_structure import put_structure
from tests.web.test_long_prose_guard import PARTS, setup


def detail(response):
    return response.json().get('detail_original') or response.json().get('detail')


def structured_book(repo, title):
    story = repo.create_story(StoryCreate(title=title))
    first = repo.create_scene(story.id, SceneCreate(title='Перша'))
    second = repo.create_scene(story.id, SceneCreate(title='Друга'))
    put_structure(repo, story.id, PARTS, {first.id: 'a1', second.id: 'b1'}, repo.get_story(story.id).revision)
    return repo.get_story(story.id)


def structure_put(client, story):
    return client.put(f'/api/stories/{story.id}/structure',
                      json={'parts': PARTS, 'scene_arcs': story.scene_arcs, 'expected_revision': story.revision})


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_on_a_book_opens_it_and_only_it(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    other = structured_book(repo, 'Інша')
    response = client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True})
    assert response.status_code == 200, response.text
    assert response.json() == {'state': 'used', 'kind': 'story', 'id': story.id, 'title': 'Книга'}
    assert structure_put(client, repo.get_story(story.id)).status_code == 200
    refused = structure_put(client, other)
    assert refused.status_code == 400 and NO_LONG_PROSE in detail(refused)
    renamed = client.patch(f'/api/stories/{other.id}', json={'title': 'Х', 'expected_revision': other.revision})
    assert renamed.status_code == 400 and READ_ONLY in detail(renamed)
    trial_book = repo.get_story(story.id)
    assert client.patch(f'/api/stories/{story.id}', json={'title': 'Х', 'expected_revision': trial_book.revision}).status_code == 200


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_needs_confirmation_and_is_single(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    response = client.post('/api/long-prose-trial', json={'story_id': story.id})
    assert response.status_code == 422 and TRIAL_CONFIRM in response.text
    assert client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True}).status_code == 200
    other = repo.create_story(StoryCreate(title='Друга'))
    again = client.post('/api/long-prose-trial', json={'story_id': other.id, 'confirm': True})
    assert again.status_code == 400 and TRIAL_USED in detail(again)


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_takes_exactly_one_target(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    assert client.post('/api/long-prose-trial', json={'confirm': True}).status_code == 422
    assert client.post('/api/long-prose-trial', json={'story_id': story.id, 'series_id': 'x', 'confirm': True}).status_code == 422


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_book_of_a_series_points_to_the_series(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    item = store.create_series(repo, 'Сага')
    book = store.create_book(repo, item.id, 'Перша')
    response = client.post('/api/long-prose-trial', json={'story_id': book.id, 'confirm': True})
    assert response.status_code == 400 and TRIAL_IN_SERIES in detail(response)


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_series_trial_lists_its_books(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, second = store.create_book(repo, item.id, 'Перша'), store.create_book(repo, item.id, 'Друга')
    store.create_bible(repo, item.id, 'Світ')
    response = client.post('/api/long-prose-trial', json={'series_id': item.id, 'confirm': True})
    assert response.status_code == 200 and response.json()['kind'] == 'series' and response.json()['title'] == 'Сага'
    from storygen.storage.long_prose_trial import trial
    assert trial(repo).books == [first.id, second.id]


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_series_with_three_books_is_refused(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    item = store.create_series(repo, 'Сага')
    for title in ('Перша', 'Друга', 'Третя'):
        store.create_book(repo, item.id, title)
    response = client.post('/api/long-prose-trial', json={'series_id': item.id, 'confirm': True})
    assert response.status_code == 400 and TRIAL_SERIES_FULL in detail(response)
    from storygen.storage.long_prose_trial import trial
    assert trial(repo) is None


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_edition_with_long_prose_needs_no_trial(tmp_path):
    client, app, repo, story, scene = setup(tmp_path)
    response = client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True})
    assert response.status_code == 400 and TRIAL_NOT_NEEDED in detail(response)


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_book_keeps_the_store_rating_limit(tmp_path, store_edition):
    client, app, repo, story, scene = setup(tmp_path)
    client.post('/api/long-prose-trial', json={'story_id': story.id, 'confirm': True})
    story = repo.get_story(story.id)
    response = client.put(f'/api/stories/{story.id}/content-rating',
                          json={'content_rating': {'sexual': 2, 'violence': 0, 'themes': 0}, 'expected_revision': story.revision})
    assert response.status_code == 400 and repo.get_story(story.id).revision == story.revision
