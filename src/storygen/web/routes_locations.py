"""MEMORY-LOCATIONS API (#67): location cards of a story, merge, split, dismissed suggestions, the author's description
and removing a model's place from a scene (R-51)."""
from fastapi import APIRouter, Request
from pydantic import Field

from ..domain import DomainModel
from ..locations import DESCRIPTION_LIMIT
from ..storage import locations as store

router = APIRouter()
ID = dict(min_length=1, max_length=64)


class Change(DomainModel):
    expected_revision: int


class Merge(Change):
    into: str = Field(**ID)


class Dismiss(Change):
    a: str = Field(**ID)
    b: str = Field(**ID)


class SceneChange(Change):
    scene_id: str = Field(**ID)


class Description(Change):
    description: str = Field(max_length=DESCRIPTION_LIMIT)


def change(request, story_id, body, action):
    return store.change_locations(request.app.state.repo, story_id, body.expected_revision, action)


@router.get('/api/stories/{story_id}/locations')
def list_locations(story_id: str, request: Request):
    return store.locations_view(request.app.state.repo, story_id)


@router.post('/api/stories/{story_id}/locations/dismiss')
def dismiss(story_id: str, body: Dismiss, request: Request):
    def action(db):
        cards = store.load_locations(db, story_id)
        if body.a not in cards or body.b not in cards or body.a == body.b:
            raise ValueError('Невідома локація')
        store.dismiss_pair(db, story_id, body.a, body.b)
    return change(request, story_id, body, action)


@router.post('/api/stories/{story_id}/locations/{location_id}/merge')
def merge(story_id: str, location_id: str, body: Merge, request: Request):
    return change(request, story_id, body, lambda db: store.merge_location(db, story_id, location_id, body.into))


@router.post('/api/stories/{story_id}/locations/{location_id}/split')
def split(story_id: str, location_id: str, body: Change, request: Request):
    return change(request, story_id, body, lambda db: store.split_location(db, story_id, location_id))


@router.post('/api/stories/{story_id}/locations/{location_id}/remove-from-scene')
def remove_from_scene(story_id: str, location_id: str, body: SceneChange, request: Request):
    repo = request.app.state.repo
    return change(request, story_id, body, lambda db: store.remove_scene_place(repo, db, story_id, location_id, body.scene_id))


@router.put('/api/stories/{story_id}/locations/{location_id}')
def describe(story_id: str, location_id: str, body: Description, request: Request):
    return change(request, story_id, body, lambda db: store.set_description(db, story_id, location_id, body.description))
