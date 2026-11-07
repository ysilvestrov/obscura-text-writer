"""Memory wire v3: grouped operations with evidence_ids; server fills category/scope and translates to journal events."""
from collections import Counter
from typing import Literal

from pydantic import Field, ValidationError, field_validator
from ..domain import DomainModel
from ..evidence import fragment_text
from .journal import CATEGORIES, MemoryEvent, _add_event, _change_event, _extend, replay_memory
from .violations import Violation, scope_unknown

ACTIONS=('add','update','retire')


def _non_blank(value):
    # Text stays byte-identical for journal IDs; only a blank claim becomes a labelled schema violation.
    if not value.strip():raise ValueError('Порожнє твердження пам’яті')
    return value


class WireAdd(DomainModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str]

    _text=field_validator('text')(_non_blank)


class WireStateAdd(WireAdd):
    character_ids: list[str]


class WireChange(DomainModel):
    claim_id: str
    text: str = Field(min_length=1)
    evidence_ids: list[str]

    _text=field_validator('text')(_non_blank)


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


def _items(wire,category):
    group=getattr(wire,category)
    return [(action,i,item) for action in ACTIONS if hasattr(group,action) for i,item in enumerate(getattr(group,action))]


def _other_wire(data):
    # wire_version only for a recognisable other wire: v2 marker, an operations key or the legacy MemoryDelta
    # shape (top-level category lists, no groups). Any other non-v3 answer is a plain schema violation.
    if data.get('schema_version')==2 or 'operations' in data:return True
    present=[data[c] for c in CATEGORIES if c in data]
    return 'schema_version' not in data and bool(present) and all(isinstance(v,list) for v in present)


GROUP_ACTIONS={'facts':('add',),'character_states':ACTIONS,'open_threads':ACTIONS,'timeline':('add',)}


def _element_model(category,action):
    if action!='add':return WireChange
    return WireStateAdd if category=='character_states' else WireAdd


def _envelope(data):
    # Shape only: labels are fixed identifiers, never keys supplied by the model.
    found=[]
    if type(data.get('schema_version')) is not int or data['schema_version']!=3 or set(data)!={'schema_version',*CATEGORIES}:
        found.append(Violation('$','schema'))
    for category in CATEGORIES:
        group=data.get(category)
        if group is None and category not in data:continue
        expected=GROUP_ACTIONS[category]
        if not isinstance(group,dict):found.append(Violation(category,'schema'));continue
        for action in ACTIONS:
            if action in group and (action not in expected or not isinstance(group[action],list)):
                found.append(Violation(f'{category}.{action}','schema'))
        if any(action not in group for action in expected) or any(key not in ACTIONS for key in group):
            found.append(Violation(category,'schema'))
    return found


def check_v3(data,previous,fragment_ids,allowed_character_ids) -> list[Violation]:
    if not isinstance(data,dict):return [Violation('$','schema')]
    if _other_wire(data):return [Violation('$','wire_version')]
    envelope=_envelope(data)
    if envelope:return envelope
    result=[];active=replay_memory(previous);allowed=set(allowed_character_ids);total=0;targets=Counter()
    for category in CATEGORIES:
        for action in GROUP_ACTIONS[category]:
            elements=data[category][action]
            total+=len(elements)
            for index,raw in enumerate(elements):
                label=f'{category}.{action}[{index}]'
                if action!='add' and isinstance(raw,dict) and isinstance(raw.get('claim_id'),str):targets[raw['claim_id']]+=1
                try:item=_element_model(category,action).model_validate(raw)
                except ValidationError:result.append(Violation(label,'schema'));continue
                ids=item.evidence_ids
                if not 1<=len(ids)<=3 or len(ids)!=len(set(ids)):result.append(Violation(label,'evidence_count'))
                if any(i not in fragment_ids for i in ids):result.append(Violation(label,'evidence_unknown'))
                if action=='add':
                    if category=='character_states' and scope_unknown(item.character_ids,allowed):
                        result.append(Violation(label,'scope_unknown'))
                    continue
                claim=active.get(item.claim_id)
                if claim is None or claim.category!=category:result.append(Violation(label,'target_unknown'))
        if len(data[category]['add'])>3:result.append(Violation(f'{category}.add','add_limit'))
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


def schema_bounds(previous,prose,allowed_character_ids) -> dict:
    # Same captured inputs as check_v3: current prose fragments, replayed journal, scene characters.
    active=replay_memory(previous)
    return {'fragment_ids':[f.id for f in fragment_text(prose)],
        'mutable':{category:[c.claim_id for c in active.values() if c.category==category] for category in ('character_states','open_threads')},
        'character_ids':list(allowed_character_ids)}


def _object(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def memory_wire_v3_schema(bounds) -> dict:
    # Only keywords the provider grammar accepts; uniqueness, non-blank text and the 12-op limit stay server-side.
    fragments=list(bounds['fragment_ids'])
    # Without fragments no element can carry evidence: forbid elements instead of an (invalid) empty enum.
    evidence_item={'type':'string','enum':fragments} if fragments else {'type':'string'}
    evidence={'type':'array','minItems':1,'maxItems':3,'items':evidence_item}
    text={'type':'string'}
    def adds(extra=None):
        props={'text':text,'evidence_ids':evidence,**(extra or {})}
        return {'type':'array','maxItems':3 if fragments else 0,'items':_object(props)}
    def changes(category):
        ids=bounds['mutable'][category]
        claim={'type':'string','enum':list(ids)} if ids else {'type':'string'}
        node={'type':'array','items':_object({'claim_id':claim,'text':text,'evidence_ids':evidence})}
        if not ids or not fragments:node['maxItems']=0
        return node
    def mutable(category,extra=None):
        return _object({'add':adds(extra),'update':changes(category),'retire':changes(category)})
    characters=bounds['character_ids']
    chars=({'type':'array','items':{'type':'string','enum':list(characters)}} if characters
        else {'type':'array','maxItems':0,'items':{'type':'string'}})
    return _object({'schema_version':{'type':'integer','enum':[3]},
        'facts':_object({'add':adds()}),
        'character_states':mutable('character_states',{'character_ids':chars}),
        'open_threads':mutable('open_threads'),
        'timeline':_object({'add':adds()})})
