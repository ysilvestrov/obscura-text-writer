"""R-47 (BUILD-EDITION-001): the long-prose checks ask about a book or a series, not the build as a whole."""
import pytest

from storygen.book.guard import (NO_LONG_PROSE, long_prose_for, require_long_prose_for, require_series_long_prose,
                                 series_long_prose, story_long_prose)
from storygen.domain import StoryCreate
from storygen.storage.repository import Repository


@pytest.mark.req('BUILD-EDITION-001')
def test_full_edition_answers_without_the_database(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    repo.db = None  # any database access fails
    assert long_prose_for(repo, story) and story_long_prose(repo, story.id) and series_long_prose(repo, 'x')
    require_long_prose_for(repo, 'missing')
    require_series_long_prose(repo, 'missing')


@pytest.mark.req('BUILD-EDITION-001')
def test_store_edition_refuses_with_the_same_text(tmp_path, store_edition):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    assert not long_prose_for(repo, story) and not story_long_prose(repo, story.id) and not series_long_prose(repo, 'x')
    for call in (lambda: require_long_prose_for(repo, 'missing'), lambda: require_series_long_prose(repo, 'missing')):
        with pytest.raises(ValueError, match=NO_LONG_PROSE):
            call()


def _claimed(repo, kind, id, books=()):
    from datetime import datetime, timezone
    from storygen.storage import long_prose_trial as trials
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        trials.claim(db, kind, id, list(books), datetime(2026, 11, 26, tzinfo=timezone.utc))


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_story_has_long_prose_and_others_do_not(tmp_path, store_edition):
    repo = Repository(tmp_path)
    trial, other = (repo.create_story(StoryCreate(title=t)) for t in ('Проба', 'Інша'))
    _claimed(repo, 'story', trial.id)
    assert long_prose_for(repo, trial) and story_long_prose(repo, trial.id)
    assert not long_prose_for(repo, other) and not story_long_prose(repo, other.id) and not story_long_prose(repo, 'missing')
    assert not series_long_prose(repo, trial.id)


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_series_trial_covers_listed_books_and_the_bible(tmp_path, store_edition):
    repo = Repository(tmp_path)
    listed, outside, bible = (repo.create_story(StoryCreate(title=t)) for t in ('Перша', 'Третя', 'Біблія'))
    listed = listed.model_copy(update={'series_id': 'ser'})
    outside = outside.model_copy(update={'series_id': 'ser'})
    bible = bible.model_copy(update={'series_id': 'ser', 'series_bible': True})
    _claimed(repo, 'series', 'ser', [listed.id])
    assert long_prose_for(repo, listed) and long_prose_for(repo, bible) and not long_prose_for(repo, outside)
    assert series_long_prose(repo, 'ser') and not series_long_prose(repo, 'other')


@pytest.mark.req('BUILD-EDITION-001')
def test_unknown_story_in_store_is_refused_with_400(tmp_path, store_edition):
    """Carried from PR 1 review: an unknown story stays 400 NO_LONG_PROSE, not 404, once the predicate reads the database."""
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    app = create_app(AppSettings(data_dir=tmp_path / 'data', env_file=tmp_path / 'absent.env'))
    response = TestClient(app, base_url='http://127.0.0.1').put('/api/stories/missing/structure',
                                                                json={'parts': [], 'scene_arcs': {}, 'expected_revision': 1})
    assert response.status_code == 400 and NO_LONG_PROSE in response.json()['detail_original'], response.text
