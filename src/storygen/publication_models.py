"""Publication data contracts, independent of generation and web."""
import re
from datetime import date
from typing import Annotated
from pydantic import Field, field_validator, model_validator
from .domain import DomainModel, Scene, Story, VersionRef, now

Identifier = Annotated[str, Field(pattern=r'^[0-9a-f]{32}$')]


class PublicationData(DomainModel):
    title: str = Field(default='',max_length=300)
    author_ids: list[Identifier] = Field(default_factory=list,max_length=20)
    language: str = Field(default='uk',max_length=63)
    genres: list[str] = Field(default_factory=list,max_length=10)
    annotation: str = Field(default='',max_length=12000)
    keywords: list[Annotated[str,Field(min_length=1,max_length=100)]] = Field(default_factory=list,max_length=30)
    cover_id: Identifier | None = None
    cycle_title: str = Field(default='',max_length=300)
    cycle_number: int | None = Field(default=None,ge=1,le=1000000)
    publication_date: str = ''
    publisher: str = Field(default='',max_length=300)
    isbn: str = Field(default='',max_length=40)
    rights: str = Field(default='',max_length=4000)
    translator_ids: list[Identifier] = Field(default_factory=list,max_length=20)
    source_language: str = Field(default='',max_length=63)

    @field_validator('title','annotation','cycle_title','publisher','rights','publication_date','language','source_language',mode='before')
    @classmethod
    def strip_text(cls,value):
        return value.strip() if isinstance(value,str) else value

    @field_validator('author_ids','translator_ids','keywords','genres')
    @classmethod
    def unique_items(cls,value):
        if len(value)!=len(set(value)) or any(not x.strip() or x!=x.strip() for x in value):
            raise ValueError('Список містить порожні значення, пробіли по краях або повтори')
        return value

    @field_validator('language','source_language')
    @classmethod
    def language_tag(cls,value,info):
        if info.field_name=='source_language' and not value:return value
        if not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*',value):
            raise ValueError('Вкажіть мовний тег, наприклад uk або en')
        return value

    @field_validator('publication_date')
    @classmethod
    def valid_date(cls,value):
        if value and (not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) or date.fromisoformat(value).isoformat()!=value):
            raise ValueError('Дата повинна мати формат YYYY-MM-DD')
        return value

    @field_validator('isbn')
    @classmethod
    def isbn_checksum(cls,value):
        value=re.sub(r'[\s-]','',value).upper()
        if not value:return value
        if re.fullmatch(r'\d{9}[\dX]',value):
            valid=sum((10-i)*(10 if c=='X' else int(c)) for i,c in enumerate(value))%11==0
        elif re.fullmatch(r'\d{13}',value):
            valid=sum(int(c)*(1 if i%2==0 else 3) for i,c in enumerate(value))%10==0
        else:valid=False
        if not valid:raise ValueError('Некоректний ISBN-10/13 або контрольна сума')
        return value

    @field_validator('genres')
    @classmethod
    def known_genres(cls,value):
        from .publication.genres import genre_catalog
        if set(value)-{code for code,label in genre_catalog()}:raise ValueError('Невідомий жанр FB2')
        return value

    @model_validator(mode='after')
    def cycle_requires_name(self):
        if self.cycle_number is not None and not self.cycle_title:raise ValueError('Для номера вкажіть назву циклу')
        return self


class PublicationCard(PublicationData):
    story_id: str
    revision: int = Field(default=0,ge=0)


class PublicSignature(DomainModel):
    id: Identifier
    display_name: str = Field(min_length=1,max_length=300)
    revision: int = Field(default=0,ge=0)
    archived_at: str | None = None
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)

    @field_validator('display_name')
    @classmethod
    def meaningful_name(cls,value):
        if not value.strip():raise ValueError('Вкажіть публічний підпис')
        return value.strip()


class CoverAsset(DomainModel):
    id: Identifier
    story_id: str
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    relative_path: str
    mime_type: str
    width: int = Field(gt=0,le=20000000)
    height: int = Field(gt=0,le=20000000)

    @model_validator(mode='after')
    def constrained_asset(self):
        suffix={'image/png':'png','image/jpeg':'jpg'}.get(self.mime_type)
        if not suffix or self.relative_path!=f'stories/{self.story_id}/publication/covers/{self.id}.{suffix}' or self.width*self.height>20000000:
            raise ValueError('Невірний ресурс обкладинки')
        return self


class PublicationView(DomainModel):
    card: PublicationCard
    effective_title: str
    authors: list[PublicSignature]
    translators: list[PublicSignature]
    cover: CoverAsset | None = None


class PublicationSnapshot(DomainModel):
    story: Story
    publication: PublicationView
    scenes: list[tuple[Scene,VersionRef | None]]
