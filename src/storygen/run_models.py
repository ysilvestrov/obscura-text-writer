"""Persistent workflow records independent of the executor and storage."""

from typing import Literal
from pydantic import Field, model_validator
from .domain import DomainModel, now


def merge_warnings(existing: str | None,messages: list[str]) -> str | None:
    lines=(existing or '').splitlines()
    for message in messages:lines.extend(message.splitlines())
    return '\n'.join(dict.fromkeys(line for line in lines if line)) or None


class RunRequest(DomainModel):
    story_id: str
    scene_id: str | None = None
    mode: Literal['stage','scene','remaining','prepare','rebuild_memory','evaluate','classify','edit_loop','publication_suggest'] = 'scene'
    edit_pass_limit: int = Field(default=5,ge=1,le=10,strict=True)
    edit_workflow: Literal['single','loop'] = 'single'
    editor_source_head: Literal['draft','prose'] | None = None
    editor_source_version_id: str | None = Field(default=None,min_length=1)
    proposal_attempt_id: str | None = None
    proposal_fingerprint: str | None = None
    stage: Literal['brief','draft','edit','memory'] | None = None
    pause_after: list[Literal['brief','draft','edit','memory']] = Field(default_factory=list)
    evaluation_mode: Literal['scene','edit_pair','story'] = 'scene'
    budget_limit_usd: str | None = None

    @model_validator(mode='after')
    def valid(self):
        if bool(self.editor_source_head) != bool(self.editor_source_version_id):
            raise ValueError('Вкажіть вид і конкретну версію джерела редактури разом')
        if self.editor_source_head and self.mode != 'edit_loop':
            raise ValueError('Явне джерело дозволено лише для окремої редактури')
        if self.mode=='publication_suggest' and self.scene_id is not None:
            raise ValueError('Пропозиція публікації належить усьому твору, не окремій сцені')
        if self.budget_limit_usd is not None:
            from .billing.models import money
            money(self.budget_limit_usd)
        if self.mode in {'stage','scene','remaining','rebuild_memory','classify','edit_loop'} and not self.scene_id:
            raise ValueError('Оберіть початкову сцену')
        if self.mode=='stage' and not self.stage:
            raise ValueError('Оберіть етап')
        if self.mode=='classify' and (not self.proposal_attempt_id or not self.proposal_fingerprint):
            raise ValueError('Оберіть точну редакторську пропозицію')
        return self


class Run(DomainModel):
    id: str
    story_id: str
    request_id: str
    request: RunRequest
    state: str = 'queued'
    tasks: list[dict]
    cursor: int = 0
    error: str | None = None
    warning: str | None = None
    editor_loop: dict | None = None
    editor_loops: dict[str,dict] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now)


class RunEvent(DomainModel):
    run_id: str
    seq: int
    type: str
    data: dict
    created_at: str = Field(default_factory=now)
