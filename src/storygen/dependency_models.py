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
    future_count: int | None = Field(default=None,ge=0,le=1000)

    @model_validator(mode='after')
    def finite_selector(self):
        allowed={
            'story': {'style_version_id','canon_version_id','characters_version_id','scene_count','tracked_characters'},
            'scene': {'title','target_words','character_ids','beats','memory_projection_policy','content_rating','memory_day_key'},
            'head': {'plan','brief','draft','prose','memory'},
            'source': {'source_plan','source_characters','source_preamble'},
            'order': {'all','prefix','narrative_window'},
        }
        if self.field not in allowed[self.kind] or not self.owner_id:
            raise ValueError('Невідомий селектор залежностей')
        if self.kind=='order' and not isinstance(self.expected,list):
            raise ValueError('Порядок повинен бути списком сцен')
        if (self.kind=='order' and self.field=='narrative_window') != (self.future_count is not None):
            raise ValueError('Ліміт майбутніх сцен дозволений і потрібний лише для narrative_window')
        return self


class MemoryReuseApproval(DependencyModel):
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    scene_id: str
    memory_id: str
    memory_scene_number: int = Field(ge=1)
    source_prose_ids: list[str]
    current_source_prose_ids: list[str]
    changed_version_count: int = Field(ge=0)
    changed_text_count: int = Field(ge=0)
    risk: bool

    @model_validator(mode='after')
    def exact_prefix(self):
        count=len(self.source_prose_ids)
        if (count!=len(self.current_source_prose_ids) or len(set(self.source_prose_ids))!=count
                or len(set(self.current_source_prose_ids))!=count
                or not 0<=self.changed_text_count<=self.changed_version_count<=count
                or self.risk!=bool(self.changed_text_count)):
            raise ValueError('Некоректна база авторського підтвердження пам’яті')
        return self


class DependencySnapshot(DependencyModel):
    schema_version: Literal[1] = 1
    scope: Literal['prepare', 'brief', 'draft', 'prose_edit', 'patches', 'memory', 'evaluation', 'author_text', 'author_rewrite']
    frozen_author_source_id: str | None = None
    selectors: list[DependencySelector]
    refs: dict[str, str]
    ref_baselines: dict[str, str | None] = Field(default_factory=dict)
    scene_order: list[str]
    accepted_stale_prose_ids: list[str] = Field(default_factory=list)
    accepted_stale_memory_ids: list[str] = Field(default_factory=list)
    memory_provenance: list[MemoryReuseApproval] = Field(default_factory=list)


    @model_validator(mode='after')
    def frozen_source_scope(self):
        if (self.scope=='author_rewrite') != bool(self.frozen_author_source_id):
            raise ValueError('Історичне джерело дозволене лише для author_rewrite')
        if self.frozen_author_source_id and self.frozen_author_source_id not in self.refs:
            raise ValueError('Історичне джерело відсутнє у refs')
        return self


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
