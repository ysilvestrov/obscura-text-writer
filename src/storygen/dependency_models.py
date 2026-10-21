"""Versioned declarative dependency contracts, independent of runtime services."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DependencyModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class DependencySelector(DependencyModel):
    kind: Literal['story', 'scene', 'head', 'source', 'order']
    owner_id: str
    field: str
    expected: str | int | bool | list[str] | None

    @model_validator(mode='after')
    def finite_selector(self):
        allowed={
            'story': {'style_version_id','canon_version_id','characters_version_id'},
            'scene': {'title','target_words','character_ids','beats'},
            'head': {'plan','brief','draft','prose','memory'},
            'source': {'source_plan','source_characters','source_preamble'},
            'order': {'all','prefix'},
        }
        if self.field not in allowed[self.kind] or not self.owner_id:
            raise ValueError('Невідомий селектор залежностей')
        if self.kind=='order' and not isinstance(self.expected,list):
            raise ValueError('Порядок повинен бути списком сцен')
        return self


class DependencySnapshot(DependencyModel):
    schema_version: Literal[1] = 1
    scope: Literal['prepare', 'brief', 'draft', 'prose_edit', 'patches', 'memory', 'evaluation', 'author_text']
    selectors: list[DependencySelector]
    refs: dict[str, str]
    ref_baselines: dict[str, str | None] = Field(default_factory=dict)
    scene_order: list[str]
    accepted_stale_prose_ids: list[str] = Field(default_factory=list)


class TargetCAS(DependencyModel):
    scene_id: str
    head: Literal['brief', 'draft', 'prose', 'memory']
    version_id: str | None
    head_revision: int = Field(ge=0)


class DependencyChange(DependencyModel):
    selector: DependencySelector | None = None
    expected: str | int | bool | list[str] | None = None
    current: str | int | bool | list[str] | None = None
    reason: str
    version_id: str | None = None


class FreshnessResult(DependencyModel):
    stale: bool
    reasons: list[DependencyChange] = Field(default_factory=list)
    baseline_id: str | None = None


class AcceptanceRecord(DependencyModel):
    id: str
    story_id: str
    scene_id: str
    version_id: str
    created_at: str
    action: Literal['accept_draft','accept_prose']
    note: str | None = None
    baseline: DependencySnapshot
    previous_baseline_id: str | None


class AcceptancePreview(DependencyModel):
    version_id: str
    expected_revision: int
    changes: list[DependencyChange]
    baseline: DependencySnapshot
    preview_fingerprint: str
    text: str
