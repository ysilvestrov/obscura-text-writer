"""Durable records for the evidence contract; old schema3 remains byte-compatible."""
from typing import Literal
from pydantic import Field
from .models import Concern,SceneReport,ReviewAcceptance


class Concern4(Concern):
    subtype: Literal['contradiction','premise_conflict','information_gap']
    statement_ids: list[str]
    provenance: list[dict]
    material: Literal['brief','prose']


class SceneReport4(SceneReport):
    schema_version: Literal[4]=4
    execution_state: Literal['complete','partial','blocked']
    concerns: list[Concern4]=Field(default_factory=list)
    diagnostics: list[dict]=Field(default_factory=list)
    suppressed: list[dict]=Field(default_factory=list)
    statements: dict[str,dict]=Field(default_factory=dict)
    authority_revisions: dict[str,int]=Field(default_factory=dict)
    unresolved_task_ids: list[str]=Field(default_factory=list)


class ReviewAcceptance4(ReviewAcceptance):
    schema_version: Literal[4]=4
    authority_revision: int=Field(ge=0,strict=True)


def report_model(raw):
    return SceneReport4 if (raw.get('schema_version') if isinstance(raw,dict) else raw.schema_version)==4 else SceneReport


def acceptance_model(raw):
    return ReviewAcceptance4 if raw.get('schema_version')==4 else ReviewAcceptance
