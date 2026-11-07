"""Memory wire v3: grouped operations with evidence_ids; server fills category/scope and translates to journal events."""
from collections import Counter
from typing import Literal

from pydantic import Field, ValidationError
from ..domain import DomainModel
from ..evidence import fragment_text
from .journal import CATEGORIES, MemoryEvent, _add_event, _change_event, _extend, replay_memory
from .violations import MUTABLE, Violation, pydantic_violations

ACTIONS=('add','update','retire')


class WireAdd(DomainModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str]


class WireStateAdd(WireAdd):
    character_ids: list[str]


class WireChange(DomainModel):
    claim_id: str
    text: str = Field(min_length=1)
    evidence_ids: list[str]


class AddOnlyGroup(DomainModel):
    add: list[WireAdd]


class StateGroup(DomainModel):
    add: list[WireStateAdd]
    update: list[WireChange]
    retire: list[WireChange]


class ThreadGroup(DomainModel):
    add: list[WireAdd]
    update: list[WireChange]
    retire: list[WireChange]


class MemoryWireV3(DomainModel):
    schema_version: Literal[3]
    facts: AddOnlyGroup
    character_states: StateGroup
    open_threads: ThreadGroup
    timeline: AddOnlyGroup


def _loc_label(loc):
    # Only fixed identifiers and indexes: keys supplied by the model never reach the label.
    if not loc or loc[0] not in CATEGORIES:return '$'
    label=loc[0]
    if len(loc)>1 and loc[1] in ACTIONS:
        label+=f'.{loc[1]}'
        if len(loc)>2 and isinstance(loc[2],int):label+=f'[{loc[2]}]'
    return label


def _items(wire,category):
    group=getattr(wire,category)
    return [(action,i,item) for action in ACTIONS if hasattr(group,action) for i,item in enumerate(getattr(group,action))]


def check_v3(data,previous,fragment_ids,allowed_character_ids) -> list[Violation]:
    if not isinstance(data,dict):return [Violation('$','schema')]
    if data.get('schema_version')!=3 or 'operations' in data:return [Violation('$','wire_version')]
    try:wire=MemoryWireV3.model_validate(data)
    except ValidationError as exc:return pydantic_violations(exc,_loc_label)
    result=[];active=replay_memory(previous);allowed=set(allowed_character_ids);total=0;targets=Counter()
    for category in CATEGORIES:
        for action,index,item in _items(wire,category):
            total+=1;label=f'{category}.{action}[{index}]'
            ids=item.evidence_ids
            if not 1<=len(ids)<=3 or len(ids)!=len(set(ids)):result.append(Violation(label,'evidence_count'))
            if any(i not in fragment_ids for i in ids):result.append(Violation(label,'evidence_unknown'))
            if action=='add':
                if category=='character_states' and not set(item.character_ids)<=allowed:
                    result.append(Violation(label,'scope_unknown'))
                continue
            targets[item.claim_id]+=1
            claim=active.get(item.claim_id)
            if claim is None or claim.category!=category:result.append(Violation(label,'target_unknown'))
        if len(getattr(wire,category).add)>3:result.append(Violation(f'{category}.add','add_limit'))
    if total>12:result.append(Violation('$','ops_limit'))
    if any(count>1 for count in targets.values()):result.append(Violation('$','target_twice'))
    return result


def wire_v3_events(wire: MemoryWireV3,previous,prose_id,prose) -> list[MemoryEvent]:
    frag={f.id:f.text for f in fragment_text(prose)}
    active=replay_memory(previous);events=[];duplicates={}
    for category in CATEGORIES:
        for action,_,item in _items(wire,category):
            quote=frag[item.evidence_ids[0]];supporting=[frag[i] for i in item.evidence_ids[1:]]
            if action=='add':
                chars=getattr(item,'character_ids',[])
                key=(category,item.text,quote,tuple(supporting))
                occurrence=duplicates.get(key,0);duplicates[key]=occurrence+1
                events.append(_add_event(category,item.text,prose_id,quote,occurrence,chars,supporting))
            else:
                claim=active[item.claim_id]
                events.append(_change_event(action,item.claim_id,item.text,category,claim.character_ids,prose_id,quote,supporting))
    return _extend(previous,prose_id,events)
