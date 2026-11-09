from fastapi import APIRouter, Request

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


@router.put('/api/scenes/{scene_id}/content-rating')
def put_scene_rating(scene_id: str,change: SceneRatingChange,request: Request):
    repo=request.app.state.repo
    if repo.get_scene(scene_id).story_id!=change.story_id:
        raise ValueError("Сцена належить іншому твору")
    return repo.update_scene_rating(scene_id,change.content_rating,change.expected_revision)
