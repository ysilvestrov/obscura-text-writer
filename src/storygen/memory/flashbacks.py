"""Flashbacks (STORY-TIME): a flashback adds facts to memory and nothing else; scenes of other arcs see the facts of
flashbacks earlier than the start of their arc («Минуле інших арок»)."""
from dataclasses import dataclass

from .journal import MemoryJournal, load_memory, replay_memory

FLASHBACK_FACTS_ONLY='Спогад додає лише факти'
FOREIGN_FACT_LIMIT=40
FOREIGN_LIMIT_WARNING='Минуле інших арок: показано {shown} фактів із {total}.'


@dataclass(frozen=True)
class ForeignFlashback:
    scene_id: str
    number: int
    memory_id: str
    time_label: str
    facts: tuple[str, ...]


def time_label(scene, language) -> str:
    """The flashback's time as the request shows it: the day label and, when the mark has one, the time."""
    from .story_time import day_key, day_label, scene_moment
    key,moment=day_key(scene),scene_moment(scene.beats)
    text=day_label(key,language) if key else ''
    if moment and moment.minutes is not None:text+=f', {moment.minutes//60:02d}:{moment.minutes%60:02d}'
    return text


def foreign_flashbacks(view, story, scenes, scene, language) -> list[ForeignFlashback]:
    """Active flashbacks above the scene in reading order, outside its lineage, with a selected fresh memory and a moment
    earlier than the start of at least one of the scene's arcs; in reading order. A book without structure has none."""
    from ..book.lineage import previous_scenes
    from ..book.story_time import arc_start
    from ..book.structure import effective_structure
    from .story_time import before, is_flashback, scene_moment
    active=sorted((s for s in scenes if not s.trashed_at),key=lambda s:s.position)
    structure=effective_structure(story,active)
    arcs=structure.arcs_of.get(scene.id,()) if structure.kind!='flat' else ()
    if not arcs:return []
    starts=[arc_start(story,active,arc) for arc in arcs]
    lineage={s.id for s in previous_scenes(story,active,scene)}
    result=[]
    for item in active:
        if item.position>=scene.position:break
        if item.id in lineage or not is_flashback(item) or not item.heads.get('memory'):continue
        moment=scene_moment(item.beats)
        if not any(before(moment,start) is True for start in starts):continue
        memory_id=item.heads['memory'];ref=view.peek_version(memory_id)
        if not ref.complete or view.is_stale(memory_id):continue
        journal=load_memory(view.read_blob(ref.relative_path,ref.sha256).decode('utf-8'))
        own=journal.source_prose_ids[-1] if journal.source_prose_ids else None
        facts=tuple(r.text for r in replay_memory(journal).values() if r.category=='facts' and r.source_version_id==own)
        result.append(ForeignFlashback(item.id,item.position+1,memory_id,time_label(item,language),facts))
    return result


def flashback_facts_value(view, story, scenes, scene) -> list[str]:
    """Value of the scene/<id>/flashback_facts selector: sorted «scene id|memory version id|time label» strings (a selector
    holds a flat list of strings)."""
    return sorted(f'{f.scene_id}|{f.memory_id}|{f.time_label}' for f in foreign_flashbacks(view,story,scenes,scene,story.language))


def foreign_section(items, language) -> tuple[str | None, str | None]:
    """The «Минуле інших арок» section and the limit warning; (None, None) without flashbacks. The latest flashbacks keep
    their facts first when the limit cuts; the section lists them in reading order. No arc or part names."""
    from ..generation.context_labels import label
    if not items:return None,None
    budget=FOREIGN_FACT_LIMIT;kept={}
    for item in reversed(items):
        kept[item.scene_id]=item.facts[:max(budget,0)];budget-=len(kept[item.scene_id])
    total=sum(len(item.facts) for item in items);shown=sum(len(v) for v in kept.values())
    blocks=[label('foreign_flashback_scene',language,number=item.number,time=item.time_label)+''.join(f'\n- {fact}' for fact in kept[item.scene_id])
        for item in items if kept[item.scene_id]]
    text=label('foreign_flashbacks',language)+'\n'+'\n'.join(blocks) if blocks else None
    return text,FOREIGN_LIMIT_WARNING.format(shown=shown,total=total) if shown<total else None


def present_only_journal(journal: MemoryJournal) -> MemoryJournal:
    """The journal a flashback writer sees in a book with arcs: no character states, hence no core either."""
    return MemoryJournal(schema_version=journal.schema_version,source_prose_ids=list(journal.source_prose_ids),
        events=[e for e in journal.events if e.category!='character_states'])


def check_flashback_journal(journal: MemoryJournal, previous: MemoryJournal) -> None:
    """A flashback journal keeps every record of the previous memory as it was; its new records are facts only."""
    old,new=replay_memory(previous),replay_memory(journal)
    if any(new.get(claim_id)!=record for claim_id,record in old.items()) or any(
            record.category!='facts' for claim_id,record in new.items() if claim_id not in old):
        raise ValueError(FLASHBACK_FACTS_ONLY)
