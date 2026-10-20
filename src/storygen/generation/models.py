from pydantic import Field

from ..domain import DomainModel, SceneCreate


class StyleProfile(DomainModel):
    genre: str = ''
    tone: str = ''
    point_of_view: str = 'третя особа'
    tense: str = 'минулий'
    rules: str = 'Українська мова. Репліки діалогу починай з довгого тире.'
    previous_tail_chars: int = Field(default=1200,ge=0,le=12000)


class SourceCitation(DomainModel):
    version_id: str
    quote: str = Field(min_length=1)


class CharacterCard(DomainModel):
    id: str
    name: str
    description: str
    sources: list[SourceCitation] = Field(min_length=1)


class StoryBlueprint(DomainModel):
    canon: str
    characters: list[CharacterCard]
    scenes: list[SceneCreate] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class WritersBrief(DomainModel):
    objective: str
    beats: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
