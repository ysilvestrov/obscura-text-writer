"""Memory wire v4: v3 groups plus mandatory per-slot core decisions and per-thread decisions; server translates to journal v3."""
from collections import Counter
from typing import Literal

from pydantic import ValidationError
from ..domain import DomainModel
from ..evidence import fragment_text
from .core import SLOT_REGISTRY_VERSION, SLOTS
from .journal import CATEGORIES, MemoryJournal, _add_event, _change_event, _extend, duplicate_key, replay_memory
from .violations import Violation, scope_unknown
from .wire_v3 import (ACTIONS, AddOnlyGroup, StateGroup, _adds, _changes, _element_model, _envelope, _object, _other_wire,
    _scope)


class CoreDecision(DomainModel):
    status: Literal['unchanged','changed','unknown','introduced']
    text: str
    evidence_ids: list[str]
    reason: str


class ThreadDecision(DomainModel):
    status: Literal['open','closed']
    resolution: str
    evidence_ids: list[str]


class MemoryWireV4(DomainModel):
    schema_version: Literal[4]
    core: dict[str,dict[str,CoreDecision]]
    threads: dict[str,ThreadDecision]
    facts: AddOnlyGroup
    character_states: StateGroup
    open_threads: AddOnlyGroup
    timeline: AddOnlyGroup


GROUP_ACTIONS={'facts':('add',),'character_states':ACTIONS,'open_threads':('add',),'timeline':('add',)}
SECTIONS=('core','threads')
# Fields each status fills; every other field of the decision must stay empty.
USED={'unchanged':(),'changed':('text','evidence_ids'),'unknown':('reason',),'introduced':('evidence_ids',),
    'open':(),'closed':('resolution','evidence_ids')}


def schema_bounds_v4(previous,prose,allowed_character_ids,tracked,day_change) -> dict:
    # Captured inputs of check_v4 and the dynamic schema; day_change is computed per tracked character upstream.
    active=replay_memory(previous);allowed=list(allowed_character_ids)
    scene=[cid for cid in tracked if cid in allowed]
    unquoted={(c.character_ids[0],c.slot) for c in active.values() if c.slot and c.source_kind=='author' and c.quote is None}
    return {'fragment_ids':[f.id for f in fragment_text(prose)],
        'mutable':{'character_states':[c.claim_id for c in active.values() if c.category=='character_states' and not c.slot]},
        'threads':[c.claim_id for c in active.values() if c.category=='open_threads'],
        'character_ids':allowed,
        'tracked':{cid:[s.name for s in SLOTS] for cid in scene},
        'unestablished':{cid:[s.name for s in SLOTS if (cid,s.name) in unquoted] for cid in scene},
        'day_change':dict(day_change),
        'slot_registry':SLOT_REGISTRY_VERSION}


def _decision(model,raw,label,fragment_ids):
    try:item=model.model_validate(raw)
    except ValidationError:return None,[Violation(label,'schema')]
    found=[];used=USED[item.status]
    for field in model.model_fields:
        if field=='status':continue
        value=getattr(item,field)
        if field not in used:
            if value:found.append(Violation(label,'schema'))
        elif field!='evidence_ids' and not value.strip():found.append(Violation(label,'schema'))
    found=found[:1]
    if 'evidence_ids' in used:
        ids=item.evidence_ids
        if not 1<=len(ids)<=3 or len(ids)!=len(set(ids)):found.append(Violation(label,'evidence_count'))
        if any(i not in fragment_ids for i in ids):found.append(Violation(label,'evidence_unknown'))
    return (None if found else item),found


def _check_decisions(data,active,bounds,fragment_ids):
    result=[];core=data['core'];tracked=bounds['tracked'];unestablished=bounds['unestablished']
    if set(core)-set(tracked):result.append(Violation('core','schema'))
    for cid,names in tracked.items():
        person=core.get(cid)
        if not isinstance(person,dict) or set(person)-set(names):result.append(Violation(f'core.{cid}','schema'))
        if not isinstance(person,dict):continue
        for name in names:
            label=f'core.{cid}.{name}'
            if name not in person:result.append(Violation(label,'schema'));continue
            item,found=_decision(CoreDecision,person[name],label,fragment_ids)
            result+=found
            if item and item.status=='introduced' and name not in unestablished.get(cid,()):
                result.append(Violation(label,'target_unknown'))
    threads=data['threads']
    if set(threads)-set(bounds['threads']):result.append(Violation('threads','schema'))
    for claim_id in bounds['threads']:
        label=f'threads.{claim_id}'
        if claim_id not in threads:result.append(Violation(label,'schema'));continue
        result+=_decision(ThreadDecision,threads[claim_id],label,fragment_ids)[1]
        claim=active.get(claim_id)
        if claim is None or claim.category!='open_threads':result.append(Violation(label,'target_unknown'))
    return result


def check_v4(data,previous,bounds) -> list[Violation]:
    if not isinstance(data,dict):return [Violation('$','schema')]
    if data.get('schema_version')==3 or _other_wire(data):return [Violation('$','wire_version')]
    envelope=_envelope(data,4,GROUP_ACTIONS,SECTIONS)
    if envelope:return envelope
    fragment_ids=set(bounds['fragment_ids']);active=replay_memory(previous);allowed=set(bounds['character_ids'])
    result=_check_decisions(data,active,bounds,fragment_ids);adds=0;targets=Counter()
    for category in CATEGORIES:
        for action in GROUP_ACTIONS[category]:
            elements=data[category][action]
            if action=='add':adds+=len(elements)
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
                # Slotted claims change only through core decisions.
                claim=active.get(item.claim_id)
                if claim is None or claim.category!=category or claim.slot:result.append(Violation(label,'target_unknown'))
        if len(data[category]['add'])>3:result.append(Violation(f'{category}.add','add_limit'))
    # Core and thread decisions are fixed by the catalog and never count toward the limit.
    if adds>12:result.append(Violation('$','ops_limit'))
    if any(count>1 for count in targets.values()):result.append(Violation('$','target_twice'))
    return result


def wire_v4_events(wire: MemoryWireV4,previous,prose_id,prose,bounds) -> MemoryJournal:
    frag={f.id:f.text for f in fragment_text(prose)}
    active=replay_memory(previous);events=[];duplicates={}
    slots={(c.character_ids[0],c.slot):c for c in active.values() if c.slot}
    def evidence(ids):return frag[ids[0]],[frag[i] for i in ids[1:]]
    def add(category,text,quote,supporting=(),chars=(),**extra):
        key=duplicate_key(category,text,quote,supporting,**extra)
        occurrence=duplicates.get(key,0);duplicates[key]=occurrence+1
        events.append(_add_event(category,text,prose_id,quote,occurrence,chars,supporting,**extra))
    def change(action,claim,text,quote,supporting=(),**extra):
        events.append(_change_event(action,claim.claim_id,text,claim.category,claim.character_ids,prose_id,quote,supporting,slot=claim.slot,**extra))
    for cid,names in bounds['tracked'].items():
        for name in names:
            decision=wire.core[cid][name];claim=slots.get((cid,name))
            if decision.status=='changed':
                quote,supporting=evidence(decision.evidence_ids)
                if claim:change('update',claim,decision.text,quote,supporting)
                else:add('character_states',decision.text,quote,supporting,[cid],slot=name)
            elif decision.status=='introduced':
                change('update',claim,claim.text,*evidence(decision.evidence_ids))
            elif decision.status=='unknown' and claim:
                # The value leaves the slot as atmosphere, keeping the original proof (or the author's unquoted word);
                # resolves_claim_id links it to the retired slot claim so it inherits that claim's hidden mark (I5).
                if claim.quote is None:quote,supporting,extra=None,[],{'source_kind':'author'}
                else:quote,supporting,extra=claim.quote,claim.supporting_quotes,{'evidence_version_id':claim.evidence_version_id or claim.source_version_id}
                change('retire',claim,claim.text,quote,supporting,**extra)
                add('character_states',claim.text,quote,supporting,[cid],resolves_claim_id=claim.claim_id,**extra)
    for claim_id in bounds['threads']:
        decision=wire.threads[claim_id]
        if decision.status=='closed':
            quote,supporting=evidence(decision.evidence_ids)
            change('retire',active[claim_id],decision.resolution,quote,supporting)
            add('facts',decision.resolution,quote,supporting,resolves_claim_id=claim_id)
    for category in CATEGORIES:
        group=getattr(wire,category)
        for action in GROUP_ACTIONS[category]:
            for item in getattr(group,action):
                quote,supporting=evidence(item.evidence_ids)
                if action=='add':add(category,item.text,quote,supporting,getattr(item,'character_ids',[]))
                else:change(action,active[item.claim_id],item.text,quote,supporting)
    return _extend(previous,prose_id,events,3)


def memory_wire_v4_schema(bounds) -> dict:
    # Same keyword set as v3; required text, unused-empty fields, evidence uniqueness and limits stay server-side.
    fragments=list(bounds['fragment_ids'])
    # Core and thread decisions repeat per slot and per thread, so their evidence items carry no fragment enum
    # (it would grow the schema with the catalog); unknown IDs are still rejected by check_v4 as evidence_unknown.
    evidence={'type':'array','minItems':0,'maxItems':3 if fragments else 0,'items':{'type':'string'}}
    text={'type':'string'}
    def status(names):
        # Without fragments evidence-bearing statuses cannot be satisfied, so they leave the enum.
        return {'type':'string','enum':[n for n in names if fragments or 'evidence_ids' not in USED[n]]}
    def slot(cid,name):
        names=['unchanged','changed','unknown']+(['introduced'] if name in bounds['unestablished'].get(cid,()) else [])
        return _object({'status':status(names),'text':text,'evidence_ids':evidence,'reason':text})
    core=_object({cid:_object({name:slot(cid,name) for name in names}) for cid,names in bounds['tracked'].items()})
    threads=_object({claim_id:_object({'status':status(['open','closed']),'resolution':text,'evidence_ids':evidence})
        for claim_id in bounds['threads']})
    states=bounds['mutable']['character_states']
    return _object({'schema_version':{'type':'integer','enum':[4]},'core':core,'threads':threads,
        'facts':_object({'add':_adds(fragments)}),
        'character_states':_object({'add':_adds(fragments,{'character_ids':_scope(bounds['character_ids'])}),
            'update':_changes(states,fragments),'retire':_changes(states,fragments)}),
        'open_threads':_object({'add':_adds(fragments)}),
        'timeline':_object({'add':_adds(fragments)})})
