"""Location cards of a story (MEMORY-LOCATIONS): created from «Локація:» lines, merged and described by the author."""
import json

from pydantic import Field

from ..domain import DomainModel, now
from ..locations import DESCRIPTION_LIMIT, Place, canonical, location_id, normalize, parse_locations, prefixes, similar


class StoryLocation(DomainModel):
    id: str
    story_id: str
    path: str                      # the first spelling, for display
    key: str                       # the normalized full path: the identity
    parent_id: str | None = None
    merged_into: str | None = None
    description: str = Field(default='', max_length=DESCRIPTION_LIMIT)
    created_at: str


def place(card: StoryLocation) -> Place:
    return Place(card.id,card.parent_id,card.merged_into)


def load_locations(db, story_id: str) -> dict[str,StoryLocation]:
    return {c.id:c for c in (StoryLocation.model_validate_json(r[0]) for r in db.execute(
        'SELECT payload FROM story_locations WHERE story_id=? ORDER BY rowid',(story_id,)))}


def _write(db, card: StoryLocation):
    db.execute('INSERT INTO story_locations VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
               (card.id,card.story_id,card.model_dump_json()))


def ensure_locations(db, story_id: str, paths) -> list[str]:
    """Card ids of the given paths in order, creating missing cards and their prefixes (each prefix is a parent)."""
    known=load_locations(db,story_id);leaves=[];stamp=None
    for parts in paths:
        parent=None
        for prefix in prefixes(parts):
            key=normalize(prefix);id=location_id(story_id,key)
            if id not in known:
                stamp=stamp or now()
                known[id]=StoryLocation(id=id,story_id=story_id,path=' / '.join(prefix),key=key,parent_id=parent,created_at=stamp)
                _write(db,known[id])
            parent=id
        leaves.append(parent)
    return leaves


def plan_location_ids(db, story_id: str, text: str) -> list[str]:
    from ..scene_plan_template import plan_fields
    return ensure_locations(db,story_id,parse_locations(plan_fields(text).get('location','')))


def _card(db, story_id, id) -> StoryLocation:
    card=load_locations(db,story_id).get(id)
    if card is None:raise ValueError('Невідома локація')
    return card


def merge_location(db, story_id: str, id: str, into: str):
    cards=load_locations(db,story_id)
    if id not in cards or into not in cards:raise ValueError('Невідома локація')
    merged={c.id:c.merged_into for c in cards.values()}
    if canonical(merged,into)==id or into==id:raise ValueError('Локацію не можна злити саму в себе')
    _write(db,cards[id].model_copy(update={'merged_into':into}))


def split_location(db, story_id: str, id: str):
    _write(db,_card(db,story_id,id).model_copy(update={'merged_into':None}))


def set_description(db, story_id: str, id: str, text: str):
    text=text.strip()
    if len(text)>DESCRIPTION_LIMIT:raise ValueError(f'Опис локації довший за {DESCRIPTION_LIMIT} знаків')
    _write(db,_card(db,story_id,id).model_copy(update={'description':text}))


def dismiss_pair(db, story_id: str, a: str, b: str):
    a,b=sorted((a,b))
    db.execute('INSERT OR IGNORE INTO location_dismissals VALUES(?,?,?)',(story_id,a,b))


def suggestions(db, story_id: str) -> list[tuple[str,str]]:
    """Pairs of unmerged cards that look alike and were not dismissed, each as (first created, second)."""
    cards=[c for c in load_locations(db,story_id).values() if not c.merged_into]
    dismissed={(r[0],r[1]) for r in db.execute('SELECT a,b FROM location_dismissals WHERE story_id=?',(story_id,))}
    found=[]
    for i,a in enumerate(cards):
        for b in cards[i+1:]:
            if tuple(sorted((a.id,b.id))) not in dismissed and similar(a.path,b.path):found.append((a.id,b.id))
    return found


def backfill(db):
    """Migration 007: location cards and Scene.location_ids of every scene, the trashed ones too; no revision moves."""
    for row in db.execute('SELECT id,story_id,payload FROM scenes').fetchall():
        data=json.loads(row['payload'])
        data['location_ids']=plan_location_ids(db,row['story_id'],data.get('beats',''))
        db.execute('UPDATE scenes SET payload=? WHERE id=?',(json.dumps(data,ensure_ascii=False),row['id']))
