"""LONG-PROSE-TRIAL (R-47): the author turns the one free trial of long prose on for a book or a series."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import model_validator

from .. import build_edition
from ..domain import DomainModel

router = APIRouter()


class TrialIn(DomainModel):
    story_id: str | None = None
    series_id: str | None = None
    confirm: bool = False

    @model_validator(mode='after')
    def one_target(self):
        if (self.story_id is None) == (self.series_id is None):
            raise ValueError('Потрібне одне з полів: story_id або series_id')
        return self


@router.post('/api/long-prose-trial')
def claim_trial(data: TrialIn, request: Request):
    from ..book.guard import TRIAL_CONFIRM, TRIAL_IN_SERIES, TRIAL_NOT_NEEDED
    from ..storage import long_prose_trial as trials
    from ..storage.series import _books, _get
    if build_edition.current().long_prose:
        raise ValueError(TRIAL_NOT_NEEDED)
    if not data.confirm:
        raise HTTPException(422, TRIAL_CONFIRM)
    repo = request.app.state.repo
    now = datetime.now(timezone.utc)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        if data.story_id is not None:
            story = repo._active_story(db, data.story_id)
            if story.series_id:
                raise ValueError(TRIAL_IN_SERIES)
            trials.claim(db, 'story', story.id, [], now)
        else:
            _get(db, data.series_id)
            books = [book.id for book in _books(db, data.series_id) if not book.series_bible]
            trials.claim(db, 'series', data.series_id, books, now)
    return trials.trial_state(repo)
