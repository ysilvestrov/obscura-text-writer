"""Versioned durable review records, independent of transport and storage."""
from typing import Literal
from pydantic import Field
from ..domain import DomainModel,new_id,now
from ..impact.models import ImpactTarget


class Concern(DomainModel):
    id: str
    kind: Literal['issue','question']
    message: str
    target_refs: list[str]=Field(default_factory=list)
    source_refs: list[str]=Field(default_factory=list)
    change_refs: list[str]=Field(default_factory=list)


class SceneReport(DomainModel):
    schema_version: Literal[3]=3
    id: str=Field(default_factory=new_id)
    story_id: str
    scene_id: str
    run_id: str
    targets: list[ImpactTarget]
    complete: bool
    concerns: list[Concern]=Field(default_factory=list)
    registry: dict[str,dict]=Field(default_factory=dict)
    part_specs: dict[str,dict]=Field(default_factory=dict)
    proofs: dict[str,str]=Field(default_factory=dict)
    coverage: dict=Field(default_factory=dict)
    created_at: str=Field(default_factory=now)


class ReviewAcceptance(DomainModel):
    schema_version: Literal[3]=3
    id: str=Field(default_factory=new_id)
    story_id: str
    scene_id: str
    run_id: str
    report_id: str
    target: ImpactTarget
    authority: Literal['model_no_concerns','author_rejected','author_revised']
    operation_id: str
    created_at: str=Field(default_factory=now)
