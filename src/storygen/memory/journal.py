"""Versioned evidence journal. Pure data and deterministic replay, no IO."""
import hashlib
import json
from collections import Counter
from typing import Literal

from pydantic import Field, model_validator
from ..domain import DomainModel
from .models import MemoryEntry, MemorySnapshot
from ..evidence import fragment_text


CATEGORIES=('facts','character_states','open_threads','timeline')
Category=Literal['facts','character_states','open_threads','timeline']


class MemoryEvent(DomainModel):
    event_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    operation: Literal['add','update','retire']
    category: Category
    text: str = Field(min_length=1)
    character_ids: list[str] = Field(default_factory=list)
    source_version_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)

    @model_validator(mode='after')
    def nonblank(self):
        if not self.text.strip() or not self.quote.strip():
            raise ValueError('Порожнє твердження або доказ пам’яті')
        return self


class MemoryJournal(DomainModel):
    schema_version: Literal[2] = 2
    source_prose_ids: list[str] = Field(default_factory=list)
    events: list[MemoryEvent] = Field(default_factory=list)

    @model_validator(mode='after')
    def valid_journal(self):
        replay_memory(self)
        return self


class MemoryOperation(DomainModel):
    action: Literal['add','update','retire']
    category: Category
    claim_id: str | None = None
    text: str = Field(min_length=1)
    character_ids: list[str] = Field(default_factory=list)
    evidence_id: str = Field(min_length=1)

    @model_validator(mode='after')
    def valid_target(self):
        if not self.text.strip():raise ValueError('Порожнє твердження пам’яті')
        if (self.action=='add')!=(self.claim_id is None):
            raise ValueError('Add не має target, update/retire потребують claim ID')
        if self.category!='character_states' and self.character_ids:
            raise ValueError('Scope дозволено лише для станів')
        return self


class MemoryOperations(DomainModel):
    schema_version: Literal[2] = 2
    operations: list[MemoryOperation] = Field(default_factory=list,max_length=12)

    @model_validator(mode='after')
    def bounded(self):
        targets=[op.claim_id for op in self.operations if op.action!='add']
        if len(targets)!=len(set(targets)):
            raise ValueError('Claim не можна змінювати двічі за відповідь')
        counts=Counter(op.category for op in self.operations if op.action=='add')
        if any(count>3 for count in counts.values()):
            raise ValueError('До трьох add на категорію')
        return self


def stable_id(prefix, value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return prefix+hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]


def replay_memory(journal: MemoryJournal) -> dict[str,MemoryEvent]:
    sources=journal.source_prose_ids
    if len(sources)!=len(set(sources)):
        raise ValueError('Повтор джерела пам’яті')
    positions={id:i for i,id in enumerate(sources)}
    active={};known=set();event_ids=set();last_position=-1
    for event in journal.events:
        if event.event_id in event_ids or event.source_version_id not in positions:
            raise ValueError('Повтор події або невідоме джерело пам’яті')
        position=positions[event.source_version_id]
        if position<last_position:
            raise ValueError('Порушено порядок джерел пам’яті')
        last_position=position;event_ids.add(event.event_id)
        if len(event.character_ids)!=len(set(event.character_ids)) or any(not id.strip() for id in event.character_ids):
            raise ValueError('Некоректний scope пам’яті')
        if event.category!='character_states' and event.character_ids:
            raise ValueError('Scope дозволено лише для станів')
        if event.operation=='add':
            if event.claim_id in known:
                raise ValueError('Повтор claim ID')
            known.add(event.claim_id);active[event.claim_id]=event
        else:
            previous=active.get(event.claim_id)
            if not previous or event.category not in {'character_states','open_threads'}:
                raise ValueError('Невідомий, закритий або незмінний claim')
            if previous.category!=event.category or previous.character_ids!=event.character_ids:
                raise ValueError('Не можна змінювати категорію або scope claim')
            if event.operation=='retire':
                del active[event.claim_id]
            else:
                active[event.claim_id]=event
    return active


def decode_memory(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Повтор JSON ключа')
            result[key]=value
        return result
    return json.loads(raw,object_pairs_hook=unique)


def load_memory(raw: str) -> MemoryJournal:
    data=decode_memory(raw)
    if not isinstance(data,dict):raise ValueError('Потрібен JSON об’єкт пам’яті')
    if 'schema_version' in data:
        return MemoryJournal.model_validate(data)
    legacy=MemorySnapshot.model_validate(data)
    positions={id:i for i,id in enumerate(legacy.source_prose_ids)}
    rows=[]
    for category in CATEGORIES:
        for index,entry in enumerate(getattr(legacy,category)):
            if entry.source_version_id not in positions:
                raise ValueError('Невідоме джерело legacy пам’яті')
            rows.append((positions[entry.source_version_id],CATEGORIES.index(category),index,category,entry))
    events=[];duplicates={}
    for _,_,_,category,entry in sorted(rows):
        value=[category,entry.text,entry.source_version_id,entry.quote]
        key=json.dumps(value,ensure_ascii=False)
        occurrence=duplicates.get(key,0);duplicates[key]=occurrence+1
        claim=stable_id('mc_',value+[occurrence])
        events.append(MemoryEvent(event_id=stable_id('me_',['add',claim]),claim_id=claim,
            operation='add',category=category,text=entry.text,source_version_id=entry.source_version_id,quote=entry.quote))
    return MemoryJournal(source_prose_ids=legacy.source_prose_ids,events=events)


def legacy_view(journal: MemoryJournal) -> MemorySnapshot:
    result=MemorySnapshot(source_prose_ids=journal.source_prose_ids.copy())
    for event in replay_memory(journal).values():
        getattr(result,event.category).append(MemoryEntry(text=event.text,
            source_version_id=event.source_version_id,quote=event.quote))
    return result


def _add_event(category,text,prose_id,quote,occurrence,characters=()):
    claim=stable_id('mc_',[category,text,prose_id,quote,occurrence])
    return MemoryEvent(event_id=stable_id('me_',['add',claim]),claim_id=claim,
        operation='add',category=category,text=text,character_ids=list(characters),
        source_version_id=prose_id,quote=quote)


def _extend(previous,prose_id,events):
    if prose_id in previous.source_prose_ids:
        raise ValueError('Джерело пам’яті вже враховане')
    return MemoryJournal(source_prose_ids=previous.source_prose_ids+[prose_id],
        events=[e.model_copy(deep=True) for e in previous.events]+events)


def apply_operations(previous,delta,prose_id,prose,allowed_character_ids):
    delta=MemoryOperations.model_validate(delta)
    fragments={fragment.id:fragment.text for fragment in fragment_text(prose)}
    events=[];duplicates={}
    for op in delta.operations:
        quote=fragments.get(op.evidence_id)
        if quote is None:raise ValueError('Невідомий фрагмент підтвердження пам’яті')
        if op.action=='add':
            if not set(op.character_ids)<=set(allowed_character_ids):
                raise ValueError('Невідомий scope персонажа')
            key=(op.category,op.text,quote)
            occurrence=duplicates.get(key,0);duplicates[key]=occurrence+1
            events.append(_add_event(op.category,op.text,prose_id,quote,occurrence,op.character_ids))
        else:
            events.append(MemoryEvent(event_id=stable_id('me_',[op.action,op.claim_id,op.text,prose_id,quote]),
                claim_id=op.claim_id,operation=op.action,category=op.category,text=op.text,
                character_ids=op.character_ids,source_version_id=prose_id,quote=quote))
    return _extend(previous,prose_id,events)


def merge_legacy_delta(previous,delta,prose_id,prose):
    return apply_operations(previous,MemoryOperations(operations=[MemoryOperation(action='add',
        category=category,text=claim.text,evidence_id=claim.evidence_id)
        for category in CATEGORIES for claim in getattr(delta,category)]),prose_id,prose,[])


def merge_legacy_snapshot(previous,snapshot,prose_id,prose):
    if snapshot.source_prose_ids!=previous.source_prose_ids+[prose_id]:
        raise ValueError('Пам’ять повинна посилатися на всі поточні джерела прози')
    active=legacy_view(previous);events=[]
    for category in CATEGORIES:
        needed=Counter(entry.model_dump_json() for entry in getattr(active,category))
        extras=[]
        for entry in getattr(snapshot,category):
            key=entry.model_dump_json()
            if needed[key]:needed[key]-=1
            else:extras.append(entry)
        if any(needed.values()):raise ValueError('Нова пам’ять втратила попередні підтверджені записи')
        duplicates={}
        for entry in extras:
            if entry.source_version_id!=prose_id or entry.quote not in prose:
                raise ValueError('Новий запис потребує підтвердження поточною прозою')
            key=(entry.text,entry.quote);occurrence=duplicates.get(key,0);duplicates[key]=occurrence+1
            events.append(_add_event(category,entry.text,prose_id,entry.quote,occurrence))
    return _extend(previous,prose_id,events)


def parse_memory_result(raw,previous,prose_id,prose,mode,allowed_character_ids,*,warnings=None):
    from .models import MemoryDelta
    data=decode_memory(raw)
    if mode=='snapshot':
        return merge_legacy_snapshot(previous,MemorySnapshot.model_validate(data),prose_id,prose)
    if isinstance(data,dict) and 'schema_version' in data:
        # Model-only wire normalization; manual journals and domain validators stay strict.
        if isinstance(data.get('operations'),list):
            for index,op in enumerate(data['operations']):
                if (isinstance(op,dict) and isinstance(op.get('category'),str) and op['category'] in {'facts','timeline','open_threads'}
                    and isinstance(op.get('character_ids'),list) and op['character_ids']
                    and all(isinstance(value,str) for value in op['character_ids'])):
                    op['character_ids']=[]
                    if warnings is not None:
                        warnings.append(f'Пам’ять: операція {index+1} ({op["category"]}) — прибрано зайві character_ids; текст і докази не змінено.')
        return apply_operations(previous,MemoryOperations.model_validate(data),prose_id,prose,allowed_character_ids)
    return merge_legacy_delta(previous,MemoryDelta.model_validate(data),prose_id,prose)


def validate_memory_journal(journal,source_versions,previous=None):
    replay_memory(journal)
    if journal.source_prose_ids!=list(source_versions):
        raise ValueError('Пам’ять повинна посилатися на всі поточні джерела прози у порядку сцен')
    for event in journal.events:
        if event.quote not in source_versions[event.source_version_id]:
            raise ValueError('Запис пам’яті не має дослівного підтвердження у прозі')
    if previous is not None:
        count=len(previous.events)
        if journal.events[:count]!=previous.events or any(e.source_version_id in previous.source_prose_ids for e in journal.events[count:]):
            raise ValueError('Нова пам’ять змінила журнал попередніх сцен')
    return journal


def normalize_manual_memory(raw,previous,prose_id,prose,allowed_character_ids):
    data=decode_memory(raw)
    if not isinstance(data,dict):raise ValueError('Потрібен JSON об’єкт пам’яті')
    if 'schema_version' not in data:
        return merge_legacy_snapshot(previous,MemorySnapshot.model_validate(data),prose_id,prose)
    journal=load_memory(raw)
    if journal.events[:len(previous.events)]!=previous.events:
        raise ValueError('Нова пам’ять змінила журнал попередніх сцен')
    if journal.source_prose_ids!=previous.source_prose_ids+[prose_id]:
        raise ValueError('Пам’ять посилається на інші джерела прози')
    events=[];mapping={};duplicates={}
    for event in journal.events[len(previous.events):]:
        if event.source_version_id!=prose_id or event.quote not in prose:
            raise ValueError('Новий запис потребує доказу поточної сцени')
        if event.operation=='add':
            if not set(event.character_ids)<=set(allowed_character_ids):
                raise ValueError('Невідомий scope персонажа')
            key=(event.category,event.text,event.quote)
            occurrence=duplicates.get(key,0);duplicates[key]=occurrence+1
            canonical=_add_event(event.category,event.text,prose_id,event.quote,occurrence,event.character_ids)
            mapping[event.claim_id]=canonical.claim_id
        else:
            claim=mapping.get(event.claim_id,event.claim_id)
            canonical=event.model_copy(update={'claim_id':claim,'event_id':stable_id('me_',
                [event.operation,claim,event.text,prose_id,event.quote])})
        events.append(canonical)
    return _extend(previous,prose_id,events)
