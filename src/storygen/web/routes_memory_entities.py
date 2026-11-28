"""MEMORY-ENTITIES-S06: author edit of the entity overlay and clearing of the model marks; CAS on the story revision."""
from fastapi import APIRouter, Request
from pydantic import Field

from ..domain import DomainModel

router=APIRouter()


class MemoryEntitiesChange(DomainModel):
    claim_id: str = Field(min_length=1,max_length=200)
    participant_ids: list[str] = Field(default_factory=list,max_length=200)
    location_ids: list[str] | None = Field(...,max_length=200)  # required: an explicit null deletes the mark (Р6)
    expected_revision: int


class MemoryEntitiesClear(DomainModel):
    expected_revision: int


@router.put('/api/stories/{story_id}/memory-entities')
def put_memory_entities(story_id: str,change: MemoryEntitiesChange,request: Request):
    return request.app.state.repo.update_memory_entities(story_id,change.claim_id,change.participant_ids,change.location_ids,change.expected_revision)


@router.post('/api/stories/{story_id}/memory-entities/clear')
def clear_memory_entities(story_id: str,change: MemoryEntitiesClear,request: Request):
    return request.app.state.repo.clear_entity_marks(story_id,change.expected_revision)
