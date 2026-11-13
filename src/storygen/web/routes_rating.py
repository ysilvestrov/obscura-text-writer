from typing import Literal

from fastapi import APIRouter, Request
from pydantic import Field

from ..domain import ContentRating, DomainModel

router=APIRouter()


class StoryRatingChange(DomainModel):
    content_rating: ContentRating
    expected_revision: int


class SceneRatingChange(DomainModel):
    story_id: str
    content_rating: ContentRating | None
    expected_revision: int


@router.put('/api/stories/{story_id}/content-rating')
def put_story_rating(story_id: str,change: StoryRatingChange,request: Request):
    return request.app.state.repo.update_story_rating(story_id,change.content_rating,change.expected_revision)


class MemoryKindChange(DomainModel):
    claim_id: str = Field(min_length=1,max_length=200)
    kind: Literal['core','atmosphere'] | None
    expected_revision: int
    # BOOK-LINEAGE-S04: the scene the author edits from; a core slot is refused only where it is core in that scene.
    scene_id: str | None = Field(default=None,min_length=1,max_length=64)


@router.put('/api/stories/{story_id}/memory-kind')
def put_memory_kind(story_id: str,change: MemoryKindChange,request: Request):
    # MEMORY-SELECT-S08: an author mark for selection; CAS on the story revision.
    return request.app.state.repo.update_memory_kind(story_id,change.claim_id,change.kind,change.expected_revision,change.scene_id)


@router.put('/api/scenes/{scene_id}/content-rating')
def put_scene_rating(scene_id: str,change: SceneRatingChange,request: Request):
    repo=request.app.state.repo
    if repo.get_scene(scene_id).story_id!=change.story_id:
        raise ValueError("Сцена належить іншому твору")
    return repo.update_scene_rating(scene_id,change.content_rating,change.expected_revision)
