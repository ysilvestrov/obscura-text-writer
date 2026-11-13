"""BOOK-STRUCTURE API: parts and arcs of a book, the arc of a scene. CAS on the story revision."""
from fastapi import APIRouter, Request
from pydantic import Field

from ..book.guard import require_long_prose
from ..domain import DomainModel

router = APIRouter()


class ArcIn(DomainModel):
    id: str | None = Field(default=None, max_length=64)
    title: str = Field(default='', max_length=200)
    protagonist_id: str | None = Field(default=None, min_length=1, max_length=64)


class PartIn(DomainModel):
    id: str | None = Field(default=None, max_length=64)
    title: str = Field(default='', max_length=200)
    arcs: list[ArcIn] = Field(default_factory=list, max_length=1000)


class StructureChange(DomainModel):
    expected_revision: int
    parts: list[PartIn] = Field(max_length=200)
    scene_arcs: dict[str, str] = Field(default_factory=dict, max_length=100000)


class Revision(DomainModel):
    expected_revision: int


class ArcAssignment(DomainModel):
    arc_id: str = Field(min_length=1, max_length=64)
    expected_revision: int


@router.put('/api/stories/{story_id}/structure')
def put_structure(story_id: str, change: StructureChange, request: Request):
    require_long_prose()
    from ..storage.book_structure import put_structure as save
    return save(request.app.state.repo, story_id, [p.model_dump() for p in change.parts], change.scene_arcs, change.expected_revision)


@router.delete('/api/stories/{story_id}/structure')
def delete_structure(story_id: str, change: Revision, request: Request):
    require_long_prose()
    from ..storage.book_structure import clear_structure
    return clear_structure(request.app.state.repo, story_id, change.expected_revision)


@router.put('/api/stories/{story_id}/scenes/{scene_id}/arc')
def put_scene_arc(story_id: str, scene_id: str, change: ArcAssignment, request: Request):
    require_long_prose()
    from ..storage.book_structure import assign_scene
    return assign_scene(request.app.state.repo, story_id, scene_id, change.arc_id, change.expected_revision)
