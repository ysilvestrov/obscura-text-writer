"""Author review of a scene's memory head: core slots and threads "was -> now", prefix quote lookup, confirmation and edits.

Responses carry the author's own memory and prose text for their UI; never log them."""
import copy
import json
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..domain import DomainModel, RevisionConflict

from ..evidence import fragment_text
from .core import SLOTS, tracked_characters
from .journal import MemoryJournal, _add_event, _change_event, decode_memory, load_memory, replay_memory
from .replay import strip_wrapper
from .story_time import day_change
from .wire_v4 import MemoryWireV4, wire_v4_events


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


def _same(old_text,new_text):
    """Equal slot values up to case, apostrophes, spacing and a final period."""
    from ..scene_description import name_key
    return old_text==new_text or (old_text is not None and new_text is not None and name_key(old_text)==name_key(new_text))


def _derived_status(cid,name,old,new,own):
    if any(e.slot==name and e.character_ids==[cid] and e.source_kind=='author' for e in own):return 'author'
    old_text=old.text if old else None;new_text=new.text if new else None
    if _same(old_text,new_text):return 'unchanged'
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
                # A 'changed' decision that restates the same value (a fresh quote for it) is shown as unchanged.
                if status=='changed' and old and new and _same(old.text,new.text):status='unchanged'
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


KEEP_UNAVAILABLE='Лишити попереднє недоступне: у цієї версії немає відповіді моделі'
QUOTE_OUTSIDE_PREFIX='Цитату не знайдено в прозі цієї або попередніх сцен'
HEAD_CHANGED='Пам’ять сцени вже змінилась. Оновіть панель; правки не збережено.'
HEAD_OUTDATED='Пам’ять сцени не відповідає поточній прозі або попереднім сценам; спершу оновіть її'
UNKNOWN_TARGET='Правка вказує на невідомий слот або лінію пам’яті'


class _Edit(DomainModel):
    text: str | None = None
    quote: str | None = None
    evidence_version_id: str | None = None

    @model_validator(mode='after')
    def filled(self):
        if self.action=='keep':
            if self.text is not None or self.quote is not None or self.evidence_version_id is not None:
                raise ValueError('«Лишити попереднє» не має значення чи цитати')
            return self
        if self.text is None or not self.text.strip():raise ValueError('Порожнє значення правки')
        if self.quote is not None and not self.quote.strip():raise ValueError('Порожня цитата правки')
        if self.evidence_version_id is not None and self.quote is None:raise ValueError('Версія доказу без цитати')
        return self


class SlotEdit(_Edit):
    kind: Literal['slot']
    character_id: str = Field(min_length=1)
    slot: str = Field(min_length=1)
    action: Literal['keep','set']


class ThreadEdit(_Edit):
    kind: Literal['thread']
    claim_id: str = Field(min_length=1)
    action: Literal['keep','close']


CoreEdit=Annotated[SlotEdit | ThreadEdit, Field(discriminator='kind')]


def _target(edit):
    return ('slot',edit.character_id,edit.slot) if edit.kind=='slot' else ('thread',edit.claim_id)


class CoreReviewBody(DomainModel):
    expected_revision: int
    memory_version_id: str = Field(min_length=1)
    edits: list[CoreEdit] = Field(default_factory=list)

    @model_validator(mode='after')
    def one_edit_per_target(self):
        targets=[_target(e) for e in self.edits]
        if len(targets)!=len(set(targets)):raise ValueError('Один слот або лінію можна правити лише раз')
        return self


def _neutral_wire(wire,bounds,edits):
    """Copy of the captured answer where every edited slot or thread keeps its previous state; author events follow."""
    data=copy.deepcopy(wire)
    for edit in edits:
        # A target outside the captured decisions (a thread opened in this scene) has nothing to keep; an author
        # entry on it is checked against the rebuilt journal.
        if edit.kind=='slot':
            decided=edit.slot in bounds['tracked'].get(edit.character_id,())
            if decided:data['core'][edit.character_id][edit.slot]={'status':'unchanged','text':'','evidence_ids':[],'reason':''}
        else:
            decided=edit.claim_id in bounds['threads']
            if decided:data['threads'][edit.claim_id]={'status':'open','resolution':'','evidence_ids':[]}
        if not decided and edit.action=='keep':raise ValueError(UNKNOWN_TARGET)
    return MemoryWireV4.model_validate(data)


def _evidence(edit,ctx,allowed):
    """(quote, evidence_version_id) of an author entry; the quote must be verbatim in the chosen prefix prose."""
    if edit.quote is None:return None,None
    version_id=edit.evidence_version_id or ctx.prose_id
    if version_id not in allowed or edit.quote not in ctx.sources[version_id]:raise ValueError(QUOTE_OUTSIDE_PREFIX)
    return edit.quote,(None if version_id==ctx.prose_id else version_id)


def _author_events(base,edits,ctx,allowed):
    active=replay_memory(base);claims={e.claim_id for e in base.events};event_ids={e.event_id for e in base.events};events=[]
    slots={(c.character_ids[0],c.slot):c for c in active.values() if c.slot}
    prose_id=ctx.prose_id
    def add(category,text,quote,characters=(),**extra):
        occurrence=0
        while True:
            event=_add_event(category,text,prose_id,quote,occurrence,characters,source_kind='author',**extra)
            if event.claim_id not in claims:break
            occurrence+=1
        claims.add(event.claim_id);events.append(event)
    for edit in edits:
        if edit.action=='keep':continue
        quote,evidence=_evidence(edit,ctx,allowed)
        if edit.kind=='slot':
            # I2: a slot belongs to one tracked character only.
            if edit.character_id not in ctx.tracked or edit.slot not in {s.name for s in SLOTS}:raise ValueError(UNKNOWN_TARGET)
            claim=slots.get((edit.character_id,edit.slot))
            if claim is None:
                if edit.character_id not in ctx.scene.character_ids:raise ValueError('Невідомий scope персонажа')
                add('character_states',edit.text,quote,[edit.character_id],slot=edit.slot,evidence_version_id=evidence)
            elif (claim.text,claim.quote,claim.source_kind,claim.evidence_version_id)!=(edit.text,quote,'author',evidence):
                occurrence=0
                while True:
                    event=_change_event('update',claim.claim_id,edit.text,claim.category,claim.character_ids,prose_id,quote,
                        slot=claim.slot,source_kind='author',evidence_version_id=evidence,occurrence=occurrence)
                    if event.event_id not in event_ids:break
                    occurrence+=1
                events.append(event)
        else:
            claim=active.get(edit.claim_id)
            if claim is None or claim.category!='open_threads':raise ValueError(UNKNOWN_TARGET)
            # The retire carries the resolution text; with a quote the resolution is also a fact (I3), linked for I5.
            events.append(_change_event('retire',claim.claim_id,edit.text,claim.category,[],prose_id,quote,
                source_kind='author',evidence_version_id=evidence))
            if quote is not None:add('facts',edit.text,quote,evidence_version_id=evidence,resolves_claim_id=claim.claim_id)
    return events


def apply_core_review(repo, scene_id: str, body: CoreReviewBody, locale: str = 'uk') -> dict:
    """Confirm the memory head, or rebuild it with the author's edits, publish and confirm the new version."""
    from .service import manual_memory_context, publish_memory_journal
    if not body.edits:
        # confirm_memory is itself the CAS on revision and head (MEMORY-CONFIRM-S02).
        repo.confirm_memory(scene_id,body.memory_version_id,body.expected_revision)
        return core_review(repo,scene_id,locale)
    scene=repo.get_scene(scene_id)
    if scene.revision!=body.expected_revision or scene.heads.get('memory')!=body.memory_version_id:raise RevisionConflict(HEAD_CHANGED)
    ctx=manual_memory_context(repo,scene_id,body.expected_revision)
    if ctx.scene.heads.get('memory')!=body.memory_version_id:raise RevisionConflict(HEAD_CHANGED)
    head=load_memory(ctx.view.read_text(body.memory_version_id))
    previous=ctx.previous
    if head.source_prose_ids!=previous.source_prose_ids+[ctx.prose_id] or head.events[:len(previous.events)]!=previous.events:
        raise ValueError(HEAD_OUTDATED)
    captured=captured_wire(repo,body.memory_version_id)
    if captured:
        wire,bounds=captured
        base=wire_v4_events(_neutral_wire(wire,bounds,body.edits),previous,ctx.prose_id,ctx.sources[ctx.prose_id],bounds)
    else:
        if any(e.action=='keep' for e in body.edits):raise ValueError(KEEP_UNAVAILABLE)
        base=head
    # A quote may come only from the selected prose of this scene or an earlier one that the journal is built on.
    allowed={s.heads['prose'] for s in _prefix(ctx.view,scene_id)}&set(ctx.sources)
    events=_author_events(base,body.edits,ctx,allowed)
    journal=MemoryJournal(schema_version=3,source_prose_ids=base.source_prose_ids,events=[*base.events,*events])
    version,published=publish_memory_journal(repo,scene_id,journal,body.expected_revision,ctx)
    # Publishing bumps the scene revision; the confirmation CAS uses the revision set_head returned.
    repo.confirm_memory(scene_id,version.id,published.revision)
    return core_review(repo,scene_id,locale)
