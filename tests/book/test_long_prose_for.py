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
