"""Small phase-specific wire3 responses; no receipt/summary or generated URLs."""
from typing import Literal
from pydantic import Field
from ..domain import DomainModel


class WireConcern(DomainModel):
    kind: Literal['issue','question']
    message: str=Field(min_length=1,max_length=400)
    change_refs: list[str]=Field(max_length=3)
    target_refs: list[str]=Field(max_length=3)
    source_refs: list[str]=Field(max_length=3)


class WireChange(DomainModel):
    change_ref: str
    before: str | None=Field(max_length=300)
    current: str | None=Field(max_length=300)
    before_refs: list[str]=Field(max_length=2)
    source_refs: list[str]=Field(max_length=2)


class DeltaResponse(DomainModel):
    complete: bool
    changes: list[WireChange]=Field(max_length=4)
    questions: list[WireConcern]=Field(max_length=4)


class CheckResponse(DomainModel):
    complete: bool
    concerns: list[WireConcern]=Field(max_length=4)
    carry_refs: list[str]=Field(max_length=8)
