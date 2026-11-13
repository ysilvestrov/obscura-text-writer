"""MEMORY-MERGE API: the state of a merge point (conflicts, carried decisions) and the author's confirmation, CAS on the
story revision and on the head memory."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from ..book.guard import require_long_prose
from ..domain import DomainModel

router = APIRouter()


class MergeDecision(DomainModel):
    choice: str = Field(min_length=1, max_length=64)
    text: str | None = Field(default=None, max_length=4000)


class MergeConfirmation(DomainModel):
    decisions: dict[str, MergeDecision] = Field(default_factory=dict, max_length=1000)
    expected_revision: int
    expected_head_memory_ids: list[str] = Field(min_length=2, max_length=100)


@router.get('/api/stories/{story_id}/memory-merges')
def get_memory_merge(story_id: str, request: Request, scene_id: str | None = None, point: Literal['book_end'] | None = None):
    from ..storage.memory_merges import merge_point, merge_state
    if (scene_id is None) == (point is None):
        raise HTTPException(422, 'Потрібен один параметр: scene_id або point=book_end')
    repo = request.app.state.repo
    view = repo.context_view(story_id)
    story = view.get_story(story_id)
    scenes = view.list_scenes(story_id)
    if scene_id is not None and scene_id not in {s.id for s in scenes}:
        raise KeyError('Сцену не знайдено')
    found = merge_point(story, scenes, scene_id=scene_id, book_end=point == 'book_end')
    if found is None:
        return {'state': 'not_needed', 'story_revision': story.revision}
    return merge_state(view, story, scenes, found)


@router.put('/api/stories/{story_id}/memory-merges/{merge_key}')
def put_memory_merge(story_id: str, merge_key: str, change: MergeConfirmation, request: Request):
    require_long_prose()
    from ..storage.memory_merges import save_merge
    decisions = {key: value.model_dump(exclude_none=True) for key, value in change.decisions.items()}
    story, version_id = save_merge(request.app.state.repo, story_id, merge_key, decisions, change.expected_revision,
                                   change.expected_head_memory_ids)
    return {'story_revision': story.revision, 'version_id': version_id}
