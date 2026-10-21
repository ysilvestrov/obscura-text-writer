"""Pure versioned character records; legacy descriptions remain unclassified."""
import hashlib
import json
from typing import Literal
from pydantic import Field,model_validator
from ..domain import DomainModel


class CharacterCitation(DomainModel):
    version_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.version_id.strip() or not self.quote.strip():raise ValueError('Порожнє джерело картки')
        return self


class CharacterEntry(DomainModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    availability: Literal['unclassified','timeless','from_scene'] = 'unclassified'
    available_from_scene_id: str | None = None
    origin: Literal['imported','author']
    sources: list[CharacterCitation] = Field(default_factory=list)

    @model_validator(mode='after')
    def valid_entry(self):
        if not self.id.strip() or not self.text.strip():raise ValueError('Порожня відомість персонажа')
        if (self.availability=='from_scene')!=bool(self.available_from_scene_id):
            raise ValueError('Оберіть першу сцену лише для from_scene')
        if self.availability!='from_scene' and self.available_from_scene_id is not None:
            raise ValueError('Зайва сцена доступності')
        if self.origin=='imported' and not self.sources:
            raise ValueError('Імпортована відомість потребує джерела')
        return self


class CharacterRecord(DomainModel):
    schema_version: Literal[2] = 2
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    entries: list[CharacterEntry] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_entries(self):
        if not self.id.strip() or not self.name.strip():raise ValueError('Порожнє ім’я персонажа')
        if len({entry.id for entry in self.entries})!=len(self.entries):raise ValueError('Повтор ID відомості')
        return self


class LegacyCharacter(DomainModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str
    sources: list[CharacterCitation] = Field(min_length=1)


def load_characters(raw: str) -> list[CharacterRecord]:
    data=json.loads(raw)
    if not isinstance(data,list):raise ValueError('Картки мають бути списком')
    cards=[]
    for item in data:
        if not isinstance(item,dict):raise ValueError('Некоректна картка персонажа')
        if 'schema_version' in item:
            card=CharacterRecord.model_validate(item)
        else:
            legacy=LegacyCharacter.model_validate(item)
            entry_id='ce_'+hashlib.sha256(json.dumps(legacy.model_dump(),ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()[:24]
            entries=[CharacterEntry(id=entry_id,text=legacy.description,origin='imported',sources=legacy.sources)] if legacy.description.strip() else []
            card=CharacterRecord(id=legacy.id,name=legacy.name,entries=entries)
        cards.append(card)
    ids=[card.id for card in cards]
    entry_ids=[entry.id for card in cards for entry in card.entries]
    if len(ids)!=len(set(ids)) or len(entry_ids)!=len(set(entry_ids)):
        raise ValueError('Повтор ID картки або відомості')
    return cards
