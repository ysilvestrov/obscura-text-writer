"""Versioned bounded-analysis manifest and direct-child model contract."""
from typing import Literal
from pydantic import Field,PrivateAttr
from ..domain import DomainModel
from ..providers.models import RoleSettings
from .models import ImpactPlan,Evidence,Finding


class PartResult(DomainModel):
    covered_ids: list[str]
    summary: str = Field(min_length=1,max_length=6000)
    verdict: Literal['no_impact','changes_required','uncertain']
    findings: list[Finding] = Field(max_length=100)
    evidence: list[Evidence] = Field(max_length=100)
    uncertainty: str | None = None


class PartResultV2(PartResult):
    target_quotes: list[str] = Field(default_factory=list,max_length=12)


class ChunkManifest(DomainModel):
    protocol: Literal[2] = 2
    wire_schema_version: Literal[1,2] = 1
    plan: ImpactPlan
    settings: RoleSettings
    prompt_text: str
    result_cap: int
    documents: dict[str,str]
    units: dict[str,dict]
    coverage: dict[str,list[list[int]]]
    tasks: list[dict]
    roots: dict[str,dict]
    _counter_runtime: object = PrivateAttr(default=None)
    local_token_counter: dict | None = None
    fingerprint: str = ''
