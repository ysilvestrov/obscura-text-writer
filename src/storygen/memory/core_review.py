"""Read-only author review of a scene's memory head: core slots and threads "was -> now", prefix quote lookup.

Responses carry the author's own memory and prose text for their UI; never log them."""
import json

from ..evidence import fragment_text
from .core import SLOTS, tracked_characters
from .journal import MemoryJournal, decode_memory, load_memory, replay_memory
from .replay import strip_wrapper
from .story_time import day_change
from .wire_v4 import MemoryWireV4


def captured_wire(repo, memory_version_id: str) -> tuple[dict, dict] | None:
    """(v4 wire data, memory_schema_bounds) of the memory attempt that produced this version, or None."""
    try:
        ref=repo.get_version(memory_version_id)
        attempts=[a for a in repo.list_attempts(ref.story_id,scene_id=ref.scene_id)
                  if a.stage=='memory' and a.result_version_id==memory_version_id]
        if not attempts:return None
        attempt=attempts[-1]
        fragments=attempt.context['fragments']
        if fragments.get('memory_wire_version')!='4':return None
        bounds=json.loads(fragments['memory_schema_bounds'])
        raw,_=strip_wrapper(repo.files.read_partial(attempt.partial_path))
        data=decode_memory(raw)
        MemoryWireV4.model_validate(data)
        if not isinstance(bounds,dict) or not isinstance(bounds.get('tracked'),dict):return None
        return data,bounds
    except Exception:
        # Deleted attempt, unreadable or foreign answer: the review falls back to the journal diff.
        return None


def _split(journal):
    """The journal the head extended (all earlier sources) and the events of the head's own source."""
    sources=journal.source_prose_ids
    if not sources:return journal,[]
    own=[e for e in journal.events if e.source_version_id==sources[-1]]
    before=MemoryJournal(schema_version=journal.schema_version,source_prose_ids=sources[:-1],
        events=[e for e in journal.events if e.source_version_id!=sources[-1]])
    return before,own


def _slots(active):
    return {(c.character_ids[0],c.slot):c for c in active.values() if c.slot}


def _derived_status(cid,name,old,new,own):
    if any(e.slot==name and e.character_ids==[cid] and e.source_kind=='author' for e in own):return 'author'
    old_text=old.text if old else None;new_text=new.text if new else None
    if old_text==new_text:return 'unchanged'
    return 'unknown' if new_text is None else 'changed'


def core_review(repo, scene_id: str, locale: str = 'uk') -> dict:
    from ..storage.snapshots import core_cards
    view=repo.scene_view(scene_id)
    scene=view.get_scene(scene_id)
    memory_id=scene.heads.get('memory')
    result={'scene_id':scene.id,'memory_version_id':memory_id,'revision':scene.revision,'has_wire':False,
            'day_change':False,'confirmation':None,'slots':[],'threads':[]}
    if not memory_id:return result
    ref=view.get_version(memory_id)
    head=load_memory(view.read_text(memory_id))
    before,own=_split(head)
    old_active=replay_memory(before);new_active=replay_memory(head)
    captured=captured_wire(repo,memory_id)
    wire,bounds=captured if captured else (None,None)
    scenes=view.list_scenes(scene.story_id)
    cards=core_cards(view,view.get_story(scene.story_id))
    tracked=list(bounds['tracked']) if bounds else tracked_characters(cards,scenes)
    if bounds:
        signal=bounds.get('day_change')
        changed=any(signal.values()) if isinstance(signal,dict) else bool(signal)
    else:changed=any(day_change(scenes,scene,cid) for cid in tracked)
    result.update(has_wire=wire is not None,day_change=changed,
        confirmation=ref.memory_confirmation.model_dump() if ref.memory_confirmation else None)
    old_slots,new_slots=_slots(old_active),_slots(new_active)
    if old_slots or new_slots:
        names={card.id:card.name for card in cards}
        for cid in tracked:
            for slot in SLOTS:
                old,new=old_slots.get((cid,slot.name)),new_slots.get((cid,slot.name))
                decision=((wire or {}).get('core') or {}).get(cid,{}).get(slot.name)
                if decision:
                    status=decision['status'];reason=(decision.get('reason') or None) if status=='unknown' else None
                else:status,reason=_derived_status(cid,slot.name,old,new,own),None
                result['slots'].append({'character_id':cid,'name':names.get(cid,cid),'slot':slot.name,
                    'label':slot.label_en if locale=='en' else slot.label_uk,
                    'before':old.text if old else None,'after':new.text if new else None,'status':status,'reason':reason,
                    'reader_unknown':bool(new and new.source_kind=='author' and new.quote is None)})
    retired={e.claim_id:e for e in own if e.category=='open_threads' and e.operation=='retire'}
    decisions=(wire or {}).get('threads') or {}
    for claim_id,claim in old_active.items():
        if claim.category!='open_threads':continue
        current=new_active.get(claim_id)
        decision=decisions.get(claim_id)
        status=decision['status'] if decision else ('open' if current else 'closed')
        closing=retired.get(claim_id)
        resolution=(decision.get('resolution') if decision else None) or (closing.text if closing else None)
        result['threads'].append({'claim_id':claim_id,'text':(current or claim).text,'status':status,
            'resolution':resolution if status=='closed' else None})
    for claim_id,claim in new_active.items():
        if claim.category=='open_threads' and claim_id not in old_active:
            result['threads'].append({'claim_id':claim_id,'text':claim.text,'status':'open','resolution':None})
    return result


def _prefix(view, scene_id):
    scene=view.get_scene(scene_id)
    return [s for s in view.list_scenes(scene.story_id) if s.position<=scene.position and s.heads.get('prose')]


def prefix_scenes(repo, scene_id: str) -> list[dict]:
    view=repo.scene_view(scene_id)
    return [{'scene_id':s.id,'scene_number':s.position+1,'title':s.title,'version_id':s.heads['prose']} for s in _prefix(view,scene_id)]


def prefix_fragments(repo, scene_id: str, query: str = '', source_scene_id: str | None = None, limit: int = 50) -> list[dict]:
    view=repo.scene_view(scene_id)
    scenes=_prefix(view,scene_id)
    needle=(query or '').strip().casefold()
    if source_scene_id is not None:
        scenes=[s for s in scenes if s.id==source_scene_id]
        if not scenes:raise ValueError('Цитату можна взяти лише з вибраної прози цієї або попередніх сцен')
    elif not needle:raise ValueError('Вкажіть сцену або текст для пошуку фрагмента')
    found=[]
    for item in scenes:
        version_id=item.heads['prose']
        for fragment in fragment_text(view.read_text(version_id)):
            if needle and needle not in fragment.text.casefold():continue
            found.append({'version_id':version_id,'scene_id':item.id,'scene_number':item.position+1,
                'fragment_id':fragment.id,'text':fragment.text})
            if len(found)>=limit:return found
    return found
