"""Bounded model-owned fields for review4; authority remains code-owned."""
from typing import Annotated,Literal
from pydantic import Field,model_validator
from ..domain import DomainModel
from .wire_models import WireChange


class Endpoint(DomainModel):
    ref: str=Field(min_length=1,max_length=100)
    start: int=Field(ge=0,strict=True)
    end: int=Field(ge=1,strict=True)
    quote: str=Field(min_length=1,max_length=512)


class Contradiction(DomainModel):
    type: Literal['contradiction']
    left: Endpoint
    right: Endpoint
    explanation: str=Field(min_length=1,max_length=400)


class InformationGap(DomainModel):
    type: Literal['information_gap']
    target: Endpoint
    source_refs: list[str]=Field(max_length=3)
    missing_information: str=Field(min_length=1,max_length=300)
    why_needed: str=Field(min_length=1,max_length=300)


Candidate=Annotated[Contradiction|InformationGap,Field(discriminator='type')]


class CheckResponse4(DomainModel):
    analysis_status: Literal['done','unable']
    reason: str|None=Field(max_length=300)
    candidates: list[Candidate]=Field(max_length=4)

    @model_validator(mode='after')
    def unable_reason(self):
        if self.analysis_status=='unable' and not (self.reason or '').strip():raise ValueError('Потрібна причина незавершеного аналізу')
        return self


class DeltaResponse4(CheckResponse4):
    candidates: list[Candidate]=Field(max_length=0)
    changes: list[WireChange]=Field(max_length=4)
