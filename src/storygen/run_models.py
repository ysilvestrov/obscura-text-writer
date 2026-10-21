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
    mode: Literal['stage','scene','remaining','prepare','rebuild_memory','evaluate'] = 'scene'
    stage: Literal['brief','draft','edit','memory'] | None = None
    pause_after: list[Literal['brief','draft','edit','memory']] = Field(default_factory=list)
    evaluation_mode: Literal['scene','edit_pair','story'] = 'scene'

    @model_validator(mode='after')
    def valid(self):
        if self.mode in {'stage','scene','remaining','rebuild_memory'} and not self.scene_id:
            raise ValueError('Оберіть початкову сцену')
        if self.mode=='stage' and not self.stage:
            raise ValueError('Оберіть етап')
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
    created_at: str = Field(default_factory=now)


class RunEvent(DomainModel):
    run_id: str
    seq: int
    type: str
    data: dict
    created_at: str = Field(default_factory=now)
