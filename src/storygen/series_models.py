"""SERIES: a series of books and the series fields of a book (long prose, project 4a)."""
from pydantic import Field, field_validator

from .domain import DomainModel, SeriesStart, now  # noqa: F401 (SeriesStart re-exported)


class Series(DomainModel):
    id: str
    revision: int = 0
    title: str = Field(min_length=1, max_length=300)
    created_at: str = Field(default_factory=now)

    @field_validator('title', mode='before')
    @classmethod
    def trimmed(cls, value):
        return ' '.join(value.split()) if isinstance(value, str) else value
