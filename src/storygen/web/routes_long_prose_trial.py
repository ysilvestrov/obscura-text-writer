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
    from ..book.guard import TRIAL_CONFIRM, TRIAL_NOT_NEEDED
    from ..storage import long_prose_trial as trials
    if build_edition.current().long_prose:
        raise ValueError(TRIAL_NOT_NEEDED)
    if not data.confirm:
        raise HTTPException(422, TRIAL_CONFIRM)
    repo = request.app.state.repo
    trials.claim_target(repo, story_id=data.story_id, series_id=data.series_id, now=datetime.now(timezone.utc))
    return trials.trial_state(repo)
