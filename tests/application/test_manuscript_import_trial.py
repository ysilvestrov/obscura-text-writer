"""R-47 (LONG-PROSE-TRIAL): a manuscript with parts can be imported as the trial book, or into the trial series."""
import pytest
from pydantic import ValidationError

from storygen import build_edition
from storygen.application import manuscript_import as service
from storygen.book.guard import NO_LONG_PROSE, TRIAL_SERIES_FULL, TRIAL_USED
from storygen.domain import StoryCreate
from storygen.storage import series as store
from storygen.storage.long_prose_trial import trial
from tests.application.test_manuscript_import_apply import body, story_files, temp_files
from tests.application.test_manuscript_import_preview import BOOK, SETTINGS, repo_for

PARTS = [{'index': 0, 'title': 'Частина'}]


def parted(preview):
    return [{'start': s.start, 'title': s.title, 'part_index': 0} for s in preview.scenes]


def claim_story(repo):
    from storygen.web.routes_long_prose_trial import TrialIn  # noqa: F401  (the route exists)
    from datetime import datetime, timezone
    from storygen.storage.long_prose_trial import claim
    story = repo.create_story(StoryCreate(title='Інша'))
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        claim(db, 'story', story.id, [], datetime.now(timezone.utc))


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_preview_offers_parts_while_the_trial_is_free(tmp_path, store_edition):
    repo = repo_for(tmp_path)
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    assert preview.edition['parts_allowed'] is True and preview.edition['series_allowed'] is False
    assert preview.edition['trial']['state'] == 'available' and preview.parts


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_parts_need_the_trial_flag(tmp_path, store_edition):
    repo = repo_for(tmp_path)
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    with pytest.raises(ValueError, match=NO_LONG_PROSE):
        service.apply_import(repo, preview.import_id, body(preview, parted(preview), parts=PARTS))
    result = service.apply_import(repo, preview.import_id, body(preview, parted(preview), parts=PARTS, trial=True))
    story = repo.get_story(result['story_id'])
    assert story.book_structure is not None
    assert trial(repo).kind == 'story' and trial(repo).id == story.id


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_used_trial_refuses_before_any_write(tmp_path, store_edition):
    repo = repo_for(tmp_path)
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    claim_story(repo)
    kept, books = temp_files(tmp_path), len(repo.list_stories(include_trashed=True))
    with pytest.raises(ValueError, match=TRIAL_USED):
        service.apply_import(repo, preview.import_id, body(preview, parted(preview), parts=PARTS, trial=True))
    assert len(repo.list_stories(include_trashed=True)) == books and temp_files(tmp_path) == kept


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_import_into_the_trial_series_takes_a_place(tmp_path, store_edition):
    repo = repo_for(tmp_path)
    item = store.create_series(repo, 'Сага', trial=True)
    store.create_book(repo, item.id, 'Перша')
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    assert preview.edition['series_allowed'] is True
    result = service.apply_import(repo, preview.import_id, body(preview, series={'series_id': item.id, 'number': 2}))
    assert result['story_id'] in trial(repo).books
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    with pytest.raises(ValueError, match=TRIAL_SERIES_FULL):
        service.apply_import(repo, preview.import_id, body(preview, series={'series_id': item.id, 'number': 3}))
    other = store.create_series(repo, 'Чужа')
    with pytest.raises(ValueError, match=NO_LONG_PROSE):
        service.apply_import(repo, preview.import_id, body(preview, series={'series_id': other.id, 'number': 1}))


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_with_a_series_is_invalid(tmp_path, store_edition):
    repo = repo_for(tmp_path)
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    with pytest.raises(ValidationError):
        service.apply_import(repo, preview.import_id, body(preview, series={'series_id': 'a' * 32, 'number': 1}, trial=True))


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_full_edition_ignores_the_trial_flag(tmp_path):
    repo = repo_for(tmp_path)
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    assert 'trial' in preview.edition and preview.edition['trial']['state'] == 'none'
    service.apply_import(repo, preview.import_id, body(preview, parted(preview), parts=PARTS, trial=True))
    assert trial(repo) is None


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_series_trial_keeps_parts_for_its_books(tmp_path, store_edition):
    """Final review I3: with a series trial, a book imported into it keeps its parts."""
    repo = repo_for(tmp_path)
    item = store.create_series(repo, 'Сага', trial=True)
    preview = service.preview(repo, BOOK, 'book.md', SETTINGS)
    assert preview.edition['parts_allowed'] is True and preview.parts
    result = service.apply_import(repo, preview.import_id,
                                  body(preview, parted(preview), parts=PARTS, series={'series_id': item.id, 'number': 1}))
    assert repo.get_story(result['story_id']).book_structure is not None
