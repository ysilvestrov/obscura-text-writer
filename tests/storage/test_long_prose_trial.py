"""R-47 (LONG-PROSE-TRIAL): the trial marker is written once; a series trial remembers two books."""
import threading
from datetime import datetime, timezone

import pytest

from storygen.book.guard import TRIAL_SERIES_FULL, TRIAL_USED
from storygen.domain import StoryCreate
from storygen.storage import long_prose_trial as trials
from storygen.storage.repository import Repository

NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)


def claim(repo, kind, id, books=()):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        return trials.claim(db, kind, id, list(books), NOW)


def admit(repo, series_id, story_id):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        trials.admit(db, series_id, story_id)


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_claim_is_written_once(tmp_path, store_edition):
    repo = Repository(tmp_path)
    first = claim(repo, 'story', 's1')
    with pytest.raises(ValueError, match=TRIAL_USED):
        claim(repo, 'series', 'x')
    assert trials.trial(repo) == first and first.kind == 'story' and first.id == 's1'


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_concurrent_claims_leave_one(tmp_path, store_edition):
    repo = Repository(tmp_path)
    results, barrier = [], threading.Barrier(2)

    def run(id):
        barrier.wait()
        try:
            claim(repo, 'story', id)
            results.append('ok')
        except ValueError as error:
            results.append(str(error))
    threads = [threading.Thread(target=run, args=(id,)) for id in ('a', 'b')]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == sorted(['ok', TRIAL_USED])


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_admit_fills_two_books_then_refuses(tmp_path, store_edition):
    repo = Repository(tmp_path)
    claim(repo, 'series', 'ser', ['b1'])
    admit(repo, 'ser', 'b2')
    admit(repo, 'ser', 'b1')  # already in: nothing changes
    with pytest.raises(ValueError, match=TRIAL_SERIES_FULL):
        admit(repo, 'ser', 'b3')
    admit(repo, 'other', 'b3')  # not the trial series: nothing to do
    assert trials.trial(repo).books == ['b1', 'b2']


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_state_for_full_reads_nothing(tmp_path):
    repo = Repository(tmp_path)
    repo.db = None
    assert trials.trial_state(repo) == {'state': 'none', 'kind': None, 'id': None, 'title': None}


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trial_state_available_then_used(tmp_path, store_edition):
    repo = Repository(tmp_path)
    assert trials.trial_state(repo)['state'] == 'available'
    story = repo.create_story(StoryCreate(title='Пробна'))
    claim(repo, 'story', story.id)
    assert trials.trial_state(repo) == {'state': 'used', 'kind': 'story', 'id': story.id, 'title': 'Пробна'}


@pytest.mark.req('LONG-PROSE-TRIAL')
def test_trashed_trial_story_is_still_used(tmp_path, store_edition):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Пробна'))
    claim(repo, 'story', story.id)
    repo.set_story_trashed(story.id, story.revision, False)
    state = trials.trial_state(repo)
    assert state['state'] == 'used' and state['title'] == 'Пробна'
