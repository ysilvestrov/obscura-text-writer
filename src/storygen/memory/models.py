from pydantic import Field

from ..domain import DomainModel


class MemoryEntry(DomainModel):
    text: str = Field(min_length=1)
    source_version_id: str
    quote: str = Field(min_length=1)


class MemorySnapshot(DomainModel):
    facts: list[MemoryEntry] = Field(default_factory=list)
    character_states: list[MemoryEntry] = Field(default_factory=list)
    open_threads: list[MemoryEntry] = Field(default_factory=list)
    timeline: list[MemoryEntry] = Field(default_factory=list)
    source_prose_ids: list[str] = Field(default_factory=list)


class MemoryClaim(DomainModel):
    text: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)


class MemoryDelta(DomainModel):
    facts: list[MemoryClaim] = Field(default_factory=list, max_length=3)
    character_states: list[MemoryClaim] = Field(default_factory=list, max_length=3)
    open_threads: list[MemoryClaim] = Field(default_factory=list, max_length=3)
    timeline: list[MemoryClaim] = Field(default_factory=list, max_length=3)
