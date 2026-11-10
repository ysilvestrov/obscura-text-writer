from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
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
    target_words: int = Field(default=7000,ge=5000)
    # STORY-LANGUAGE: prose and model instructions; fixed once the story has model output.
    language: Literal['uk','en'] = 'uk'


class ContentRating(DomainModel):
    sexual: Literal[0,1,2]
    violence: Literal[0,1,2]
    themes: Literal[0,1,2]


class Story(StoryCreate):
    trashed_at: str | None = None
    content_rating: ContentRating | None = None
    initial_content_rating: ContentRating | None = None
    id: str
    revision: int = 0
    config_revision: int = 0
    style_version_id: str | None = None
    canon_version_id: str | None = None
    characters_version_id: str | None = None
    # Author marks for memory selection (#60, MEMORY-SELECT-S08); act only when selection runs.
    memory_kind_overrides: dict[str,Literal['core','atmosphere']] = Field(default_factory=dict,max_length=10000)
    created_at: str = Field(default_factory=now)


class SceneCreate(DomainModel):
    author_scene_number: int | None = Field(default=None,ge=0)
    title: str = Field(min_length=1,max_length=300)
    beats: str = ""
    position: int | None = Field(default=None,ge=0)
    target_words: int = Field(default=1000,ge=1)
    character_ids: list[str] = Field(default_factory=list)
    # STORY-LANGUAGE: prose language of this scene only; None follows the story language.
    prose_language: Literal['uk','en'] | None = None


class Scene(SceneCreate):
    memory_forwarding: dict[str,bool] = Field(default_factory=dict,max_length=10000)
    trashed_at: str | None = None
    trashed_position: int | None = None
    id: str
    story_id: str
    position: int
    revision: int = 0
    heads: dict[str,str] = Field(default_factory=dict)
    head_revisions: dict[str,int] = Field(default_factory=dict)
    needs_review: bool = False
    content_rating: ContentRating | None = None


VersionKind = Literal["source_plan","source_characters","character_cards","scene_plan","canon","style","prompt","brief","draft","edited","manual","memory","evaluation"]


class PromptContract(DomainModel):
    stage: Literal['prepare', 'brief', 'draft', 'edit', 'memory']
    mode: Literal['blueprint', 'brief', 'prose', 'patches', 'diff', 'snapshot', 'evidence_delta']
    schema_version: Literal[1, 2, 3, 4]


class MemoryConfirmation(DomainModel):
    confirmed_at: str
    by: Literal['author'] = 'author'


class BriefLink(DomainModel):
    """Author's word that the prose rests on this brief, with who was introduced in the scene (#44)."""
    brief_version_id: str = Field(min_length=1)
    introduced: list[str] = Field(default_factory=list,max_length=1000)
    confirmed_at: str
    by: Literal['author'] = 'author'


class AuthorLineage(DomainModel):
    """Same-scene version a manual save was made from; metadata only, never a dependency (#44)."""
    parent_version_id: str = Field(min_length=1)


class GhostRewriteStats(DomainModel):
    """Ghost Mode rewrite of an AI draft (#55). Metadata only: not in sha256, dependencies or request hashes.

    blocks/overlap are computed by the server; peeks, peek_ms and pastes_blocked are the browser's word."""
    source_draft_id: str = Field(min_length=1)
    blocks: int = Field(ge=0)
    blocks_written: int = Field(ge=0)
    blocks_skipped: int = Field(ge=0)
    peeks: int = Field(ge=0)
    peek_ms: int = Field(ge=0)
    pastes_blocked: int = Field(ge=0)
    overlap_4gram: float | None = Field(default=None,ge=0,le=1)
    min_block_chars: int = Field(ge=1)


class VersionRef(DomainModel):
    id: str
    story_id: str
    scene_id: str | None
    kind: VersionKind
    format: Literal["text","json"] = "text"
    content_format: Literal['plain','markdown'] = 'plain'
    sha256: str
    relative_path: str
    source_run_id: str | None = None
    complete: bool = True
    stale: bool = False
    manual_projection_policy: list[str] | None = Field(default=None,max_length=10000)
    dependency_snapshot: DependencySnapshot | None = None
    prompt_contract: PromptContract | None = None
    input_refs: list[str] = Field(default_factory=list)
    memory_confirmation: MemoryConfirmation | None = None
    brief_link: BriefLink | None = None
    author_lineage: AuthorLineage | None = None
    ghost_rewrite: GhostRewriteStats | None = None
    created_at: str = Field(default_factory=now)

    @model_validator(mode='after')
    def author_text_format(self):
        if self.content_format=='markdown' and (self.kind not in {'draft','edited','manual'} or self.format!='text'):
            raise ValueError('Markdown дозволено лише для текстових версій чернетки та прози')
        return self


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
