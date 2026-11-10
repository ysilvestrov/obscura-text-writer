"""Deterministic views; proof data never enters the literary memory section."""
import json
from dataclasses import dataclass
from .journal import CATEGORIES, MemoryJournal, replay_memory
from ..generation.context_labels import label


@dataclass(frozen=True)
class MemoryProjection:
    text: str
    metrics: dict


def memory_catalog(journal: MemoryJournal) -> str:
    return json.dumps([{'claim_id':event.claim_id,'category':event.category,
        'text':event.text,'character_ids':event.character_ids}
        for event in replay_memory(journal).values()],ensure_ascii=False,separators=(',',':'))


def memory_catalog_v3(journal: MemoryJournal) -> str:
    # Facts/timeline cannot be updated, so their IDs stay out of the model's reach.
    mutable,immutable=[],[]
    for event in replay_memory(journal).values():
        if event.category in {'character_states','open_threads'}:
            mutable.append({'claim_id':event.claim_id,'category':event.category,'text':event.text,'character_ids':event.character_ids})
        else:immutable.append({'category':event.category,'text':event.text})
    return json.dumps({'mutable':mutable,'immutable':immutable},ensure_ascii=False,separators=(',',':'))


def memory_catalog_v4(journal: MemoryJournal, tracked: list[str], names: dict[str,str], *, all_tracked: list[str] | None = None,
        keep: set[str] | None = None) -> str:
    # Core shows every registry slot of the tracked characters (empty ones as null); threads are decided by claim_id.
    # tracked is the cast's share of all_tracked (default: the same list); slots of a character outside all_tracked
    # (former protagonist) are listed as ordinary mutable states, as schema_bounds_v4 does. keep (MEMORY-SELECT-S07) narrows
    # mutable states and immutable records to these claim IDs; the core and threads are never narrowed.
    from .core import SLOTS
    every=set(tracked if all_tracked is None else all_tracked)
    active=replay_memory(journal).values()
    slots={(e.character_ids[0],e.slot):e for e in active if e.slot}
    def value(event):
        if event is None:return {'value':None,'source':None,'reader_unknown':False}
        return {'value':event.text,'source':event.source_kind,'reader_unknown':event.source_kind=='author' and event.quote is None}
    core={cid:{s.name:value(slots.get((cid,s.name))) for s in SLOTS} for cid in tracked}
    threads=[{'claim_id':e.claim_id,'text':e.text} for e in active if e.category=='open_threads']
    mutable=[{'claim_id':e.claim_id,'category':e.category,'text':e.text,'character_ids':e.character_ids}
        for e in active if e.category=='character_states' and (not e.slot or e.character_ids[0] not in every)
        and (keep is None or e.claim_id in keep)]
    immutable=[{'category':e.category,'text':e.text} for e in active if e.category in {'facts','timeline'}
        and (keep is None or e.claim_id in keep)]
    return json.dumps({'names':{cid:names.get(cid,cid) for cid in tracked},'core':core,'threads':threads,
        'mutable':mutable,'immutable':immutable},ensure_ascii=False,separators=(',',':'))


READER_UNKNOWN=label('memory_reader_unknown','uk')


def reader_unknown(event, language='uk'):
    # An author's word without a quote is unknown to the reader wherever it is rendered: in the core or, after
    # an unknown decision, as an ordinary atmosphere state.
    return label('memory_reader_unknown',language) if event.source_kind=='author' and event.quote is None else ''


LABELS={category:label('memory_'+category,'uk') for category in ('facts','character_states','open_threads','timeline')}


@dataclass(frozen=True)
class MemoryItem:
    """One rendered line of the literary memory section with what selection (#60) needs to place it."""
    claim_id: str
    section: str                 # 'core' or a journal category
    owner: str | None            # tracked character of a core line
    line: str
    text: str
    character_ids: tuple[str,...]
    slot: str | None
    source_scene: int | None     # scene of the event that produced this line


def _timeline_events(journal):
    # A v4 closure is shown only as its resolution fact; a legacy retire without one stays in the timeline.
    resolved={e.resolves_claim_id for e in journal.events if e.resolves_claim_id}
    return [e for e in journal.events if e.category=='timeline'
        or e.category=='open_threads' and e.operation=='retire' and e.claim_id not in resolved]


def candidate_claim_ids(journal) -> set[str]:
    """Claims memory_items can render (before the scene filter): active ones and timeline entries, including legacy thread
    closures without a resolution fact (#60, MEMORY-SELECT-S08)."""
    return set(replay_memory(journal))|{e.claim_id for e in _timeline_events(journal)}


def memory_items(journal: MemoryJournal, character_ids: list[str], source_scene_numbers: dict[str,int], *, hidden_claim_ids=(),
        forwarded_claim_ids=(), tracked=(), names=None, language='uk') -> tuple[list[MemoryItem],dict]:
    from .core import SLOTS
    from .forwarding import effective_hidden
    active=replay_memory(journal)
    hidden=effective_hidden(journal,hidden_claim_ids,forwarded=forwarded_claim_ids)
    items=[];omitted=0;core_lines=0
    item=lambda event,section,line,owner=None:MemoryItem(event.claim_id,section,owner,line,event.text,tuple(event.character_ids),
        event.slot,source_scene_numbers.get(event.source_version_id))
    # The core is a mandatory layer: first, never filtered by the scene cast, only by MEMORY-FORWARD.
    slots={(e.character_ids[0],e.slot):e for e in active.values() if e.slot and e.character_ids[0] in tracked}
    for cid in tracked:
        for slot in SLOTS:
            event=slots.get((cid,slot.name))
            if event is None or event.claim_id in hidden:continue
            items.append(item(event,'core',f'{slot.label_en if language=="en" else slot.label_uk}: {event.text}'+reader_unknown(event,language),cid));core_lines+=1
    for category in CATEGORIES:
        if category=='timeline':
            entries=_timeline_events(journal)
        else:
            entries=[e for e in active.values() if e.category==category
                and not (e.slot and e.character_ids[0] in tracked)]
        for event in entries:
            if event.claim_id in hidden:continue
            if category=='character_states' and character_ids and event.character_ids and not set(character_ids).intersection(event.character_ids):
                omitted+=1;continue
            scene=source_scene_numbers.get(event.source_version_id)
            prefix=label('memory_scene_prefix',language,number=scene) if category=='timeline' and scene is not None else ''
            items.append(item(event,category,'— '+prefix+event.text+reader_unknown(event,language)))
    return items,{'journal_chars':len(journal.model_dump_json()),'event_count':len(journal.events),'active_claim_count':len(active),
        'omitted_state_count':omitted,'core_line_count':core_lines,'hidden_claim_count':len(hidden&{e.claim_id for e in journal.events})}


def render_memory(items, tracked, names=None, *, timeline_note: str | None = None, language='uk') -> str:
    sections=[]
    for cid in tracked:
        lines=[i.line for i in items if i.section=='core' and i.owner==cid]
        if lines:
            # Without a card name the technical ID never reaches the literary section; tracked is the protagonist.
            owner=(names or {}).get(cid) or label('memory_protagonist',language)
            sections.append(label('memory_core_owner',language,name=owner)+'\n'+'\n'.join(lines))
    for category in CATEGORIES:
        lines=[i.line for i in items if i.section==category]
        if category=='timeline' and timeline_note:lines.insert(0,'— '+timeline_note)
        sections.append(label('memory_'+category,language)+'\n'+('\n'.join(lines) if lines else label('memory_none',language)))
    return '\n\n'.join(sections)


def project_memory(journal: MemoryJournal, character_ids: list[str], source_scene_numbers: dict[str,int], *, hidden_claim_ids=(),
        forwarded_claim_ids=(), tracked=(), names=None, language='uk') -> MemoryProjection:
    items,metrics=memory_items(journal,character_ids,source_scene_numbers,hidden_claim_ids=hidden_claim_ids,
        forwarded_claim_ids=forwarded_claim_ids,tracked=tracked,names=names,language=language)
    text=render_memory(items,tracked,names,language=language)
    return MemoryProjection(text,{'projection_version':'memory-uk-v3','journal_chars':metrics['journal_chars'],
        'event_count':metrics['event_count'],'active_claim_count':metrics['active_claim_count'],
        'projection_chars':len(text),'omitted_state_count':metrics['omitted_state_count'],'core_line_count':metrics['core_line_count'],
        'hidden_claim_count':metrics['hidden_claim_count']})
