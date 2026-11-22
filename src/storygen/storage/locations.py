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
    every=load_locations(db,story_id);cards=[c for c in every.values() if not c.merged_into]
    dismissed={(r[0],r[1]) for r in db.execute('SELECT a,b FROM location_dismissals WHERE story_id=?',(story_id,))}
    def ancestors(card):
        seen=set()
        while card.parent_id and card.parent_id not in seen and card.parent_id in every:
            seen.add(card.parent_id);card=every[card.parent_id]
        return seen
    lineage={c.id:ancestors(c) for c in cards}
    found=[]
    for i,a in enumerate(cards):
        for b in cards[i+1:]:
            # A place and a place inside it share words by construction; that is nesting, not a duplicate.
            if a.id in lineage[b.id] or b.id in lineage[a.id]:continue
            if tuple(sorted((a.id,b.id))) not in dismissed and similar(a.path,b.path):found.append((a.id,b.id))
    return found


def view_locations(view) -> dict[str,StoryLocation]:
    """Cards of the view's story; every ContextView loads them with the rest of its snapshot."""
    return view.locations


def scene_neighbourhood(cards: dict[str,StoryLocation], location_ids) -> list[str]:
    from ..locations import neighbourhood
    return neighbourhood({id:place(c) for id,c in cards.items()},location_ids)


def scene_cards(cards: dict[str,StoryLocation], location_ids) -> list[str]:
    """Card ids of the scene locations and their ancestors, ancestors first, merged cards as their target."""
    merged={c.id:c.merged_into for c in cards.values()};out=[]
    for id in location_ids:
        chain=[];id=canonical(merged,id)
        while id in cards and id not in chain:
            chain.append(id);parent=cards[id].parent_id
            id=canonical(merged,parent) if parent else None
        out+=[item for item in reversed(chain) if item not in out]
    return out


def shown_locations(cards: dict[str,StoryLocation], location_ids) -> list[list[str]]:
    """[path, description] of scene_cards: what «ЛОКАЦІЇ СЦЕНИ» shows."""
    return [[cards[id].path,cards[id].description] for id in scene_cards(cards,location_ids)]


def backfill(db):
    """Migration 007: location cards and Scene.location_ids of every scene, the trashed ones too; no revision moves."""
    for row in db.execute('SELECT id,story_id,payload FROM scenes').fetchall():
        data=json.loads(row['payload'])
        data['location_ids']=plan_location_ids(db,row['story_id'],data.get('beats',''))
        db.execute('UPDATE scenes SET payload=? WHERE id=?',(json.dumps(data,ensure_ascii=False),row['id']))


def locations_view(repo, story_id: str) -> dict:
    """MEMORY-LOCATIONS-S07: cards of a story with the active scenes that name each card (merged names count for the
    target) and the open suggestions; the story revision guards every change."""
    view=repo.context_view(story_id)
    story=view.get_story(story_id);cards=view_locations(view)
    merged={c.id:c.merged_into for c in cards.values()}
    scenes={id:[] for id in cards}
    for scene in sorted(view.list_scenes(story_id),key=lambda s:s.position):
        for id in dict.fromkeys(canonical(merged,id) for id in scene.location_ids):
            if id in scenes:scenes[id].append({'id':scene.id,'position':scene.position,'title':scene.title})
    with repo.db.connection() as db:
        pairs=suggestions(db,story_id)
    return {'story_revision':story.revision,
            'locations':[{'id':c.id,'path':c.path,'parent_id':c.parent_id,'merged_into':c.merged_into,
                          'target_path':cards[canonical(merged,c.id)].path if c.merged_into else None,
                          'description':c.description,'scenes':scenes[c.id]} for c in cards.values()],
            'suggestions':[{'a':a,'b':b,'a_path':cards[a].path,'b_path':cards[b].path} for a,b in pairs]}


def change_locations(repo, story_id: str, expected_revision: int, action) -> dict:
    """Applies action(db) to the cards of a story under CAS on its revision, which moves on by one."""
    from ..domain import RevisionConflict
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:
            raise RevisionConflict('Твір уже змінено. Оновіть локації; зміну не збережено.')
        action(db)
        repo._save_story(db,story.model_copy(update={'revision':story.revision+1}))
    return locations_view(repo,story_id)
