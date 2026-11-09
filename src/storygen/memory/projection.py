"""Deterministic views; proof data never enters the literary memory section."""
import json
from dataclasses import dataclass
from .journal import CATEGORIES, MemoryJournal, replay_memory


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


def memory_catalog_v4(journal: MemoryJournal, tracked: list[str], names: dict[str,str]) -> str:
    # Core shows every registry slot of the tracked characters (empty ones as null); threads are decided by claim_id.
    from .core import SLOTS
    active=replay_memory(journal).values()
    slots={(e.character_ids[0],e.slot):e for e in active if e.slot}
    def value(event):
        if event is None:return {'value':None,'source':None,'reader_unknown':False}
        return {'value':event.text,'source':event.source_kind,'reader_unknown':event.source_kind=='author' and event.quote is None}
    core={cid:{s.name:value(slots.get((cid,s.name))) for s in SLOTS} for cid in tracked}
    threads=[{'claim_id':e.claim_id,'text':e.text} for e in active if e.category=='open_threads']
    mutable=[{'claim_id':e.claim_id,'category':e.category,'text':e.text,'character_ids':e.character_ids}
        for e in active if e.category=='character_states' and not e.slot]
    immutable=[{'category':e.category,'text':e.text} for e in active if e.category in {'facts','timeline'}]
    return json.dumps({'names':{cid:names.get(cid,cid) for cid in tracked},'core':core,'threads':threads,
        'mutable':mutable,'immutable':immutable},ensure_ascii=False,separators=(',',':'))


READER_UNKNOWN=' (читачеві невідомо: якщо знадобиться, введи в тексті як нове)'


def project_memory(journal: MemoryJournal, character_ids: list[str], source_scene_numbers: dict[str,int], *, hidden_claim_ids=(),
        forwarded_claim_ids=(), tracked=(), names=None) -> MemoryProjection:
    from .core import SLOTS
    from .forwarding import effective_hidden
    active=replay_memory(journal)
    hidden=effective_hidden(journal,hidden_claim_ids,forwarded=forwarded_claim_ids)
    labels={'facts':'ФАКТИ','character_states':'ПОТОЧНІ СТАНИ',
        'open_threads':'ВІДКРИТІ ЛІНІЇ','timeline':'ХРОНОЛОГІЯ'}
    sections=[];omitted=0;core_lines=0
    # The core is a mandatory layer: first, never filtered by the scene cast, only by MEMORY-FORWARD.
    slots={(e.character_ids[0],e.slot):e for e in active.values() if e.slot and e.character_ids[0] in tracked}
    for cid in tracked:
        lines=[]
        for slot in SLOTS:
            event=slots.get((cid,slot.name))
            if event is None or event.claim_id in hidden:continue
            lines.append(f'{slot.label_uk}: {event.text}'+(READER_UNKNOWN if event.source_kind=='author' and event.quote is None else ''))
        if lines:
            # Without a card name the technical ID never reaches the literary section; tracked is the protagonist.
            sections.append(f'ЯДРО СТАНУ — {(names or {}).get(cid) or "протагоніст"}\n'+'\n'.join(lines));core_lines+=len(lines)
    # A v4 closure is shown only as its resolution fact; a legacy retire without one stays in the timeline.
    resolved={e.resolves_claim_id for e in journal.events if e.resolves_claim_id}
    for category in CATEGORIES:
        lines=[]
        if category=='timeline':
            entries=[e for e in journal.events if e.category=='timeline'
                or e.category=='open_threads' and e.operation=='retire' and e.claim_id not in resolved]
        else:
            entries=[e for e in active.values() if e.category==category
                and not (e.slot and e.character_ids[0] in tracked)]
        for event in entries:
            if event.claim_id in hidden:continue
            if category=='character_states' and character_ids and event.character_ids and not set(character_ids).intersection(event.character_ids):
                omitted+=1;continue
            scene=source_scene_numbers.get(event.source_version_id)
            prefix=f'Сцена {scene}: ' if category=='timeline' and scene is not None else ''
            lines.append('— '+prefix+event.text)
        sections.append(labels[category]+'\n'+('\n'.join(lines) if lines else 'Немає.'))
    text='\n\n'.join(sections)
    return MemoryProjection(text,{'projection_version':'memory-uk-v3','journal_chars':len(journal.model_dump_json()),
        'event_count':len(journal.events),'active_claim_count':len(active),
        'projection_chars':len(text),'omitted_state_count':omitted,'core_line_count':core_lines,
        'hidden_claim_count':len(hidden&{e.claim_id for e in journal.events})})
