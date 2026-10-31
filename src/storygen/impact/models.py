"""Typed impact inputs and model outputs; no I/O or inference."""
import hashlib
import json
from typing import Literal
from pydantic import Field,model_validator
from ..domain import DomainModel,new_id,now


def fingerprint(value):
    if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class Evidence(DomainModel):
    source_id: str
    quote: str = Field(min_length=1,max_length=16000)


class SourceChange(DomainModel):
    id: str
    label: str
    input_kind: str
    input_field: str
    owner_id: str
    old_ref: str | None = None
    new_ref: str | None = None
    old_text: str
    new_text: str
    changed: bool


TEXT_STAMP_EXCLUDE={'fingerprint','group_id','memory_id','memory_sha256','memory_text','memory_source_hashes','memory_evidence_status'}


class ImpactTarget(DomainModel):
    story_id: str
    scene_id: str
    scene_title: str
    position: int
    material: Literal['brief','prose']
    version_id: str
    sha256: str
    content_format: str
    text: str
    changes: list[SourceChange]
    source_hashes: dict[str,str]
    selectors: list[dict]
    baseline_ids: dict[str,str | None]
    order: list[str]
    memory_id: str | None
    memory_sha256: str | None = None
    memory_text: str = ''
    memory_source_hashes: dict[str,str] = Field(default_factory=dict)
    memory_evidence_status: Literal['missing','current','historical','invalid'] = 'missing'
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str = ''
    group_id: str = ''


class ImpactPlan(DomainModel):
    story_id: str
    targets: list[ImpactTarget]
    fingerprint: str


class DeltaItem(DomainModel):
    change_ids: list[str] = Field(min_length=1,max_length=1000)
    category: Literal['fact','time','knowledge','motivation','relationship','thread','style','wording','other']
    before: str
    after: str
    explanation: str = Field(min_length=1,max_length=8000)
    evidence: list[Evidence] = Field(max_length=100)


class DeltaReport(DomainModel):
    covered_change_ids: list[str]
    items: list[DeltaItem] = Field(max_length=300)
    uncertainty: str | None = None


class Finding(DomainModel):
    target_quote: str = Field(min_length=1,max_length=16000)
    change_ids: list[str] = Field(min_length=1,max_length=1000)
    explanation: str = Field(min_length=1,max_length=8000)
    evidence: list[Evidence] = Field(min_length=1,max_length=100)


class MaterialVerdict(DomainModel):
    version_id: str
    verdict: Literal['no_impact','changes_required','uncertain']
    covered_change_ids: list[str]
    explanation: str = Field(min_length=1,max_length=12000)
    findings: list[Finding] = Field(max_length=100)

    @model_validator(mode='after')
    def meaningful(self):
        if (self.verdict=='changes_required')!=bool(self.findings):
            raise ValueError('Конкретні проблеми потрібні лише для changes_required')
        return self


class CheckReport(DomainModel):
    materials: list[MaterialVerdict] = Field(min_length=1,max_length=2)
    memory_semantic_impact: Literal['none_found','possible','unchecked']
    memory_explanation: str = Field(min_length=1,max_length=8000)


class ImpactRecord(DomainModel):
    schema_version: Literal[1,2] = 1
    chunk_manifest: dict | None = None
    proof_attempt_ids: dict[str,str] = Field(default_factory=dict)
    id: str = Field(default_factory=new_id)
    story_id: str
    run_id: str
    attempt_id: str
    target: ImpactTarget
    delta_attempt_id: str
    verdict: MaterialVerdict
    memory_semantic_impact: Literal['none_found','possible','unchecked']
    memory_explanation: str
    created_at: str = Field(default_factory=now)


class ImpactApplication(DomainModel):
    id: str = Field(default_factory=new_id)
    story_id: str
    record_id: str
    version_id: str
    action: Literal['apply','reject']
    created_at: str = Field(default_factory=now)
