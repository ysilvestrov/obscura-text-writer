"""CAS for the memory-entities overlay (MEMORY-ENTITIES-S06): author edits and model batches; no journal, prose or scene writes."""
from typing import Literal, Mapping

from ..domain import MemoryEntityMark, RevisionConflict, Story
from .context_view import ContextView

MAX_ENTITY_MARKS=20000
CONFLICT='Твір уже змінено. Оновіть таблицю; розмітку сутностей не збережено.'


def book_claims(view,story_id: str) -> dict:
    """Candidate records (MEMORY-ENTITIES, Р9) of the memory heads of every active scene, newest scene first; the first seen wins."""
    from ..memory.kinds import _journal
    from ..memory.projection import candidate_events
    found={}
    for scene in sorted(view.peek_scenes(story_id),key=lambda s:s.position,reverse=True):
        if scene.trashed_at:continue
        memory_id=scene.heads.get('memory')
        journal=_journal(view,memory_id) if memory_id else None
        if journal is None:continue
        try:events=candidate_events(journal)
        except ValueError:continue
        for claim_id,event in events.items():found.setdefault(claim_id,event)
    return found


def _known_cards(view,story) -> frozenset[str]:
    from ..characters.models import load_characters
    if not story.characters_version_id:return frozenset()
    return frozenset(c.id for c in load_characters(view.read_text(story.characters_version_id)))


def entity_resolver(view,story):
    """The resolver of the story's overlay: cards of the current characters version, merges of the location cards."""
    from ..memory.entities import EntityResolver
    merged={c.id:c.merged_into for c in view.locations.values()}
    return EntityResolver(story.memory_entities,_known_cards(view,story),merged)


def entities_value(view,scene_id) -> dict[str,str]:
    """Selector value scene/memory_entities (Р8): candidates of the memory before the scene whose effective entities differ
    from the ones without the overlay; peek only, an unreadable memory gives {}."""
    from ..memory.previous import previous_memory, read_previous_journal
    from ..memory.projection import candidate_events
    scene=view.peek_scene(scene_id)
    story=view.peek_story(scene.story_id)
    if not story.memory_entities:return {}
    before=previous_memory(view,scene,peek=True,require=False)
    try:journal=read_previous_journal(view,before,peek=True) if before.memory_id else None
    except (ValueError,KeyError,OSError):journal=None
    if journal is None:return {}
    try:events=candidate_events(journal)
    except ValueError:return {}
    resolver=entity_resolver(view,story);bare=resolver.bare();found={}
    for claim_id in sorted(events):
        if claim_id not in story.memory_entities:continue
        e=events[claim_id];args=(claim_id,e.category,e.participant_ids,e.location_ids)
        now,plain=resolver.of(*args),bare.of(*args)
        if (now.participant_ids,now.location_ids)!=(plain.participant_ids,plain.location_ids):
            found[claim_id]=f"p={','.join(now.participant_ids)};l={','.join(now.location_ids)}"
    return found


def _check_ids(view,story,participant_ids,location_ids):
    cards=_known_cards(view,story)
    if any(i not in cards for i in participant_ids):raise ValueError('Невідомий персонаж у розмітці сутностей')
    if any(i not in view.locations for i in location_ids):raise ValueError('Невідома локація в розмітці сутностей')


def _transaction(repo,story_id,expected_revision,change):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:raise RevisionConflict(CONFLICT)
        marks=dict(story.memory_entities)
        view=ContextView(repo,db,story_id)
        result=change(view,story,marks)
        if marks==story.memory_entities:return story,result
        story=story.model_copy(update={'memory_entities':marks,'revision':story.revision+1})
        repo._save_story(db,story)
        return story,result


def update_memory_entities(repo,story_id: str,claim_id: str,participant_ids: list[str],location_ids: list[str] | None,expected_revision: int) -> Story:
    """The author sets both fields of a record (Р16); location_ids=None removes the mark of any source (Р6)."""
    def change(view,story,marks):
        if location_ids is None:
            marks.pop(claim_id,None);return
        event=book_claims(view,story_id).get(claim_id)
        if event is None:raise ValueError('Запису немає в пам’яті твору')
        _check_ids(view,story,participant_ids,location_ids)
        if participant_ids and event.category=='character_states':
            raise ValueError('Учасники дозволені лише для ліній, фактів і хронології')
        mark=MemoryEntityMark(participant_ids=list(participant_ids),location_ids=list(location_ids),source='author')
        if marks.get(claim_id)==mark:return
        if claim_id not in marks and len(marks)>=MAX_ENTITY_MARKS:raise ValueError('Забагато записів розмітки сутностей')
        marks[claim_id]=mark
    return _transaction(repo,story_id,expected_revision,change)[0]


def apply_entity_marks(repo,story_id: str,marks: Mapping[str,tuple[list[str],list[str]]],expected_revision: int) -> tuple[Story,list[str]]:
    """A model batch (Р10: refused whole on an unknown record, card or location); never overwrites an author mark (І4)."""
    def change(view,story,stored):
        claims=book_claims(view,story_id);applied=[]
        for claim_id,(people,places) in marks.items():
            if claim_id not in claims:raise ValueError('Запису немає в пам’яті твору')
            _check_ids(view,story,people,places)
        for claim_id,(people,places) in marks.items():
            current=stored.get(claim_id)
            if current is not None and current.source=='author':continue
            people=[] if claims[claim_id].category=='character_states' else list(people)
            if not people and not places:
                if current is not None:del stored[claim_id];applied.append(claim_id)
                continue
            mark=MemoryEntityMark(participant_ids=people,location_ids=list(places),source='model')
            if current==mark:continue
            if current is None and len(stored)>=MAX_ENTITY_MARKS:raise ValueError('Забагато записів розмітки сутностей')
            stored[claim_id]=mark;applied.append(claim_id)
        return applied
    return _transaction(repo,story_id,expected_revision,change)


def clear_entity_marks(repo,story_id: str,expected_revision: int,source: Literal['model']='model') -> Story:
    """Removes every model mark; author marks are removed one by one (Р15)."""
    if source!='model':raise ValueError('Скасувати можна лише розмітку моделі')
    def change(view,story,marks):
        for claim_id in [c for c,m in marks.items() if m.source==source]:del marks[claim_id]
    return _transaction(repo,story_id,expected_revision,change)[0]
