from ..domain import DomainModel, now
from pydantic import Field


class RunEvent(DomainModel):
    run_id: str
    seq: int
    type: str
    data: dict
    created_at: str = Field(default_factory=now)
