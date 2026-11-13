"""Import publication payloads shared by authoring and storage."""
from typing import Literal
from pydantic import Field
from .domain import DomainModel, SceneCreate

class ImportedScene(DomainModel):
    data: SceneCreate
    plan_version_id: str
    # BOOK-STRUCTURE: part and arc titles from the plan; None continues the book's current part or arc.
    part_title: str | None=Field(default=None,max_length=200)
    arc_title: str | None=Field(default=None,max_length=200)
    part_index: int | None=Field(default=None,ge=0,le=10000)
    # BOOK-LINEAGE-S04: «Протагоніст:» of the scene plan, resolved by card name at publication.
    protagonist_name: str | None=Field(default=None,max_length=200)
    # MEMORY-MERGE harness: «Арки:» of a meeting scene (two or more arc titles of its part).
    arc_titles: list[str] | None=Field(default=None,max_length=20)

class ImportPublication(DomainModel):
    metadata: dict
    active_plan_version_id: str | None=None
    active_characters_version_id: str | None=None
    character_cards_version_id: str | None=None
    scenes: list[ImportedScene]=Field(default_factory=list)
    structured: bool=False

class ImportPublicationResult(DomainModel):
    revision: int
    created_scene_ids: list[str]=Field(default_factory=list)
    # BOOK-LINEAGE-S04: (arc_id, name) not resolved at publication — retried at the end of the batch.
    pending_protagonists: list[tuple[str,str]]=Field(default_factory=list)
    warnings: list[str]=Field(default_factory=list)


class ImportFileResult(DomainModel):
    client_index: int
    name: str
    kind: Literal['source_plan','source_characters']
    status: Literal['imported','failed','not_processed']='not_processed'
    source_id: str | None=None
    version_id: str | None=None
    created_scene_ids: list[str]=Field(default_factory=list)
    created_character_cards: int=0
    skipped_character_names: list[str]=Field(default_factory=list)
    skipped_scene_numbers: list[int]=Field(default_factory=list)
    warnings: list[str]=Field(default_factory=list)
    error: str | None=None
