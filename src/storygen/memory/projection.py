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


def project_memory(journal: MemoryJournal, character_ids: list[str], source_scene_numbers: dict[str,int], *, hidden_claim_ids=()) -> MemoryProjection:
    active=replay_memory(journal)
    labels={'facts':'ФАКТИ','character_states':'ПОТОЧНІ СТАНИ',
        'open_threads':'ВІДКРИТІ ЛІНІЇ','timeline':'ХРОНОЛОГІЯ'}
    sections=[];omitted=0
    for category in CATEGORIES:
        lines=[]
        if category=='timeline':
            entries=[e for e in journal.events if e.category=='timeline'
                or e.category=='open_threads' and e.operation=='retire']
        else:
            entries=[e for e in active.values() if e.category==category]
        for event in entries:
            if event.claim_id in hidden_claim_ids:continue
            if category=='character_states' and character_ids and event.character_ids and not set(character_ids).intersection(event.character_ids):
                omitted+=1;continue
            scene=source_scene_numbers.get(event.source_version_id)
            prefix=f'Сцена {scene}: ' if category=='timeline' and scene is not None else ''
            lines.append('— '+prefix+event.text)
        sections.append(labels[category]+'\n'+('\n'.join(lines) if lines else 'Немає.'))
    text='\n\n'.join(sections)
    return MemoryProjection(text,{'projection_version':'memory-uk-v2','journal_chars':len(journal.model_dump_json()),
        'event_count':len(journal.events),'active_claim_count':len(active),
        'projection_chars':len(text),'omitted_state_count':omitted,
        'hidden_claim_count':len(set(hidden_claim_ids)&{e.claim_id for e in journal.events})})
