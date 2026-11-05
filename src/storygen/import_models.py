"""Import publication payloads shared by authoring and storage."""
from pydantic import Field
from .domain import DomainModel, SceneCreate

class ImportedScene(DomainModel):
    data: SceneCreate
    plan_version_id: str

class ImportPublication(DomainModel):
    metadata: dict
    active_plan_version_id: str | None=None
    active_characters_version_id: str | None=None
    character_cards_version_id: str | None=None
    scenes: list[ImportedScene]=Field(default_factory=list)

class ImportPublicationResult(DomainModel):
    revision: int
    created_scene_ids: list[str]=Field(default_factory=list)
