from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from .dependency_models import DependencySnapshot


def new_id() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class RevisionConflict(ValueError):
    pass


class StorageCorruption(ValueError):
    pass


class StoryCreate(DomainModel):
    title: str = Field(min_length=1,max_length=300)
    target_words: int = Field(default=7000,ge=5000,le=15000)


class Story(StoryCreate):
    trashed_at: str | None = None
    id: str
    revision: int = 0
    config_revision: int = 0
    style_version_id: str | None = None
    canon_version_id: str | None = None
    characters_version_id: str | None = None
    created_at: str = Field(default_factory=now)


class SceneCreate(DomainModel):
    title: str = Field(min_length=1,max_length=300)
    beats: str = ""
    position: int | None = Field(default=None,ge=0)
    target_words: int = Field(default=1000,ge=1,le=15000)
    character_ids: list[str] = Field(default_factory=list)


class Scene(SceneCreate):
    trashed_at: str | None = None
    trashed_position: int | None = None
    id: str
    story_id: str
    position: int
    revision: int = 0
    heads: dict[str,str] = Field(default_factory=dict)
    head_revisions: dict[str,int] = Field(default_factory=dict)
    needs_review: bool = False


VersionKind = Literal["source_plan","source_characters","character_cards","scene_plan","canon","style","prompt","brief","draft","edited","manual","memory","evaluation"]


class VersionRef(DomainModel):
    id: str
    story_id: str
    scene_id: str | None
    kind: VersionKind
    format: Literal["text","json"] = "text"
    sha256: str
    relative_path: str
    source_run_id: str | None = None
    complete: bool = True
    stale: bool = False
    dependency_snapshot: DependencySnapshot | None = None
    input_refs: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now)


class StageAttempt(DomainModel):
    id: str
    run_id: str | None = None
    story_id: str
    scene_id: str | None
    stage: str
    state: str = 'running'
    context: dict
    partial_path: str
    result_version_id: str | None = None
    usage: dict = Field(default_factory=dict)
    finish_reason: str | None = None
    error: str | None = None
    created_at: str = Field(default_factory=now)
