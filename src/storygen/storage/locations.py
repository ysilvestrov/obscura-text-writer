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


def catalogue_cards(cards: dict[str,StoryLocation]) -> list[StoryLocation]:
    """Canonical (unmerged) cards in creation order: the location catalogue of CHARACTER-EXTRACT (R-51, spec 2, 3.1)."""
    return [card for card in cards.values() if not card.merged_into]


def cards_digest(cards: dict[str,StoryLocation]) -> str:
    """sha256 of every card's id, path and merge target: a new card, a merge or a split changes it."""
    import hashlib
    rows=[[card.id,card.path,card.merged_into] for card in cards.values()]
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()


PLACE_TRASHED, PLACE_PROSE_CHANGED, PLACE_NOT_AUTHOR, PLACE_PLANNED, PLACE_NOTHING = (
    'trashed', 'prose_changed', 'not_author', 'planned', 'nothing')


def apply_places_in_transaction(repo, db, story_id: str, items) -> tuple[dict[str,str|None], list[str]]:
    """Places accepted from a CHARACTER-EXTRACT proposal (spec 2, 4.3) on the caller's write transaction. `items` are
    (scene id, prose version read by the run, paths in order). Returns ({scene id: skip code or None when written}, the
    location cards created). Scenes are read from the transaction, so a cast written just before keeps its revision. A
    path whose canonical card the scene already holds is dropped; the rest get their cards from `ensure_locations` (a
    merged card's path gives that card, which `canonical` leads to its target)."""
    from ..domain import Scene,VersionRef
    from ..scene_plan_template import plan_fields
    from .scene_cast import AUTHOR_PROSE
    from .scene_metadata import stale_scene_material
    before=set(load_locations(db,story_id));outcome={}
    for scene_id,version_id,paths in items:
        row=db.execute('SELECT payload FROM scenes WHERE id=? AND story_id=?',(scene_id,story_id)).fetchone()
        scene=Scene.model_validate_json(row[0]) if row is not None else None
        prose_id=scene.heads.get('prose') if scene is not None else None
        if scene is None or scene.trashed_at:outcome[scene_id]=PLACE_TRASHED;continue
        if not prose_id or prose_id!=version_id:outcome[scene_id]=PLACE_PROSE_CHANGED;continue
        if repo._get(db,'versions',prose_id,VersionRef).kind!=AUTHOR_PROSE:outcome[scene_id]=PLACE_NOT_AUTHOR;continue
        if plan_fields(scene.beats).get('location'):outcome[scene_id]=PLACE_PLANNED;continue  # the plan line always wins
        merged={card.id:card.merged_into for card in load_locations(db,story_id).values()}
        held={canonical(merged,id) for id in scene.location_ids};new=[]
        for path in paths:
            parts=tuple(part.strip() for part in path.split('/') if part.strip())
            card=canonical(merged,location_id(story_id,normalize(parts)))
            if card not in held:held.add(card);new.append(parts)
        if not new:outcome[scene_id]=PLACE_NOTHING;continue
        scene.location_ids=list(dict.fromkeys([*scene.location_ids,*ensure_locations(db,story_id,new)]))
        scene.location_source='model'
        stale_scene_material(repo,db,scene)
        scene.revision+=1
        repo._save_scene(db,scene)
        outcome[scene_id]=None
    if any(code is None for code in outcome.values()):repo._touch_story(db,story_id)
    return outcome,[id for id in load_locations(db,story_id) if id not in before]


def remove_scene_place(repo, db, story_id: str, id: str, scene_id: str):
    """MEMORY-LOCATIONS-S08: the author removes a place a model gave the scene (R-51, spec 2, amendment 2), on the
    transaction of `change_locations`, which moves the story revision. Every scene id whose card leads to the same
    canonical card goes; a scene left without places reads as `plan` again. A place from the plan line is changed in
    the plan."""
    from ..domain import Scene
    from .scene_metadata import stale_scene_material
    cards=load_locations(db,story_id)
    if id not in cards:raise ValueError('Невідома локація')
    row=db.execute('SELECT payload FROM scenes WHERE id=? AND story_id=?',(scene_id,story_id)).fetchone()
    scene=Scene.model_validate_json(row[0]) if row is not None else None
    if scene is None or scene.trashed_at:raise ValueError('Невідома сцена')
    if scene.location_source!='model':raise ValueError('Місце сцени з плану: змініть рядок «Локація:»')
    merged={card.id:card.merged_into for card in cards.values()};target=canonical(merged,id)
    kept=[item for item in scene.location_ids if canonical(merged,item)!=target]
    if len(kept)==len(scene.location_ids):raise ValueError('Сцена не має цього місця')
    scene.location_ids=kept
    if not kept:scene.location_source='plan'
    stale_scene_material(repo,db,scene)
    scene.revision+=1
    repo._save_scene(db,scene)


def story_glues(db, story_id: str) -> list[str]:
    """Story.location_glues read on the caller's connection (a write transaction sees its own changes)."""
    row=db.execute('SELECT payload FROM stories WHERE id=?',(story_id,)).fetchone()
    return list(json.loads(row[0]).get('location_glues',[])) if row is not None else []


def plan_location_ids(db, story_id: str, text: str) -> list[str]:
    from ..scene_plan_template import plan_fields
    return ensure_locations(db,story_id,parse_locations(plan_fields(text).get('location',''),story_glues(db,story_id)))


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


GLUE_LIMIT, GLUE_MIN, GLUE_MAX = 500, 3, 200


def _plan_scenes(db, story_id: str, active_only: bool = False):
    """Scenes whose places come from a non-empty «Локація:» line, in book order (trashed ones too unless active_only)."""
    from ..domain import Scene
    from ..scene_plan_template import plan_fields
    for row in db.execute('SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id',(story_id,)).fetchall():
        scene=Scene.model_validate_json(row[0])
        if active_only and scene.trashed_at:continue
        value=plan_fields(scene.beats).get('location','')
        if value and scene.location_source=='plan':yield scene,value


def _recompute_plan_places(repo, db, story_id: str, old_glues, new_glues) -> list[tuple[list[str],list[str]]]:
    """MEMORY-LOCATIONS-S10: plan scenes whose line parses differently under the new glues than under the old ones get
    the new places; a changed scene stales its material and moves its revision, like a plan save. A scene the glue
    change does not touch keeps its stored places even when they hold an older parse (no reparse migration). Returns
    (ids before, ids after) of the changed scenes."""
    from .scene_metadata import stale_scene_material
    changed=[]
    for scene,value in list(_plan_scenes(db,story_id)):
        paths=parse_locations(value,new_glues)
        if paths==parse_locations(value,old_glues):continue
        before=list(scene.location_ids);after=ensure_locations(db,story_id,paths)
        if after==before:continue
        scene.location_ids=after
        stale_scene_material(repo,db,scene)
        scene.revision+=1
        repo._save_scene(db,scene)
        changed.append((before,after))
    return changed


def _with_ancestors(cards: dict[str,StoryLocation], ids) -> set[str]:
    out=set()
    for id in ids:
        while id and id in cards and id not in out:
            out.add(id);id=cards[id].parent_id
    return out


def _write_glues(repo, db, story_id: str, glues: list[str]):
    story=repo._active_story(db,story_id)
    repo._save_story(db,story.model_copy(update={'location_glues':glues}))


def glue_location(repo, db, story_id: str, phrase: str):
    """«Склеїти»: the phrase becomes a story glue, plan scenes are recomputed and the suggestions between the new cards
    and the cards the changed scenes held before (with their ancestors) are dismissed."""
    from ..locations import glue_key
    phrase=' '.join((phrase or '').split())
    glues=story_glues(db,story_id)
    if '/' in phrase:raise ValueError('Склеїти можна лише фразу без «/»')
    if not GLUE_MIN<=len(phrase)<=GLUE_MAX:raise ValueError(f'Фраза має бути від {GLUE_MIN} до {GLUE_MAX} знаків')
    if glue_key(phrase) in {glue_key(g) for g in glues}:raise ValueError('Цю назву вже склеєно')
    if len(parse_locations(phrase,glues))<2:raise ValueError('Фраза не охоплює жодного розрізу')
    if len(glues)>=GLUE_LIMIT:raise ValueError(f'Склеєних назв може бути не більше {GLUE_LIMIT}')
    known=set(load_locations(db,story_id))
    _write_glues(repo,db,story_id,[*glues,phrase])
    changed=_recompute_plan_places(repo,db,story_id,glues,[*glues,phrase])
    cards=load_locations(db,story_id);new=set(cards)-known
    old=set()
    for before,after in changed:old|=_with_ancestors(cards,before)-_with_ancestors(cards,after)
    for a in new:
        for b in old:
            if a!=b:dismiss_pair(db,story_id,a,b)


def unglue_location(repo, db, story_id: str, key: str):
    """«Розклеїти»: the glue goes and plan scenes are recomputed; cards and merges stay."""
    from ..locations import glue_key
    glues=story_glues(db,story_id);kept=[g for g in glues if glue_key(g)!=key]
    if len(kept)==len(glues):raise ValueError('Невідома склеєна назва')
    _write_glues(repo,db,story_id,kept)
    _recompute_plan_places(repo,db,story_id,glues,kept)


def glue_candidates(db, story_id: str) -> list[dict]:
    """Every cut between neighbouring paths in the «Локація:» lines of active plan scenes, one per phrase key, with the
    existing leaf cards on both sides of every occurrence and the scenes, in book order. A cut whose cards do not exist
    (a line stored under an older parse) offers nothing: the panel hangs the action on a card."""
    from ..locations import glue_cuts, glue_key
    glues=story_glues(db,story_id);found={};cards=set(load_locations(db,story_id))
    for scene,value in _plan_scenes(db,story_id,active_only=True):
        for phrase,left,right in glue_cuts(value,glues):
            ids=[id for id in (location_id(story_id,normalize(left)),location_id(story_id,normalize(right))) if id in cards]
            if not ids:continue
            item=found.setdefault(glue_key(phrase),{'phrase':phrase,'key':glue_key(phrase),'card_ids':[],'scene_ids':[]})
            for id in ids:
                if id not in item['card_ids']:item['card_ids'].append(id)
            if scene.id not in item['scene_ids']:item['scene_ids'].append(scene.id)
    return list(found.values())


def dismiss_pair(db, story_id: str, a: str, b: str):
    a,b=sorted((a,b))
    db.execute('INSERT OR IGNORE INTO location_dismissals VALUES(?,?,?)',(story_id,a,b))


def suggestions(db, story_id: str) -> list[tuple[str,str]]:
    """Pairs of unmerged cards that look alike and were not dismissed, each as (first created, second)."""
    every=load_locations(db,story_id);cards=[c for c in every.values() if not c.merged_into]
    dismissed={(r[0],r[1]) for r in db.execute('SELECT a,b FROM location_dismissals WHERE story_id=?',(story_id,))}
    merged={c.id:c.merged_into for c in every.values()}
    def ancestors(card):
        # Followed through merges: a parent merged elsewhere makes its target an ancestor too.
        seen=set();parent=card.parent_id
        while parent:
            for id in (parent,canonical(merged,parent)):
                if id in every:seen.add(id)
            parent=canonical(merged,parent)
            if parent not in every or every[parent].parent_id in seen:break
            parent=every[parent].parent_id
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
    target; `source` says whether the scene's places come from its plan or a model) and the open suggestions; the story
    revision guards every change."""
    view=repo.context_view(story_id)
    story=view.get_story(story_id);cards=view_locations(view)
    merged={c.id:c.merged_into for c in cards.values()}
    scenes={id:[] for id in cards}
    for scene in sorted(view.list_scenes(story_id),key=lambda s:s.position):
        for id in dict.fromkeys(canonical(merged,id) for id in scene.location_ids):
            if id in scenes:scenes[id].append({'id':scene.id,'position':scene.position,'title':scene.title,
                                               'source':scene.location_source})
    from ..locations import glue_key
    with repo.db.connection() as db:
        pairs=suggestions(db,story_id);candidates=glue_candidates(db,story_id)
    return {'story_revision':story.revision,
            'glues':[{'key':glue_key(phrase),'phrase':phrase} for phrase in story.location_glues],
            'glue_candidates':candidates,
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
        before=_shown_by_scene(db,story_id)
        action(db)
        after=_shown_by_scene(db,story_id)
        story=repo._active_story(db,story_id)  # re-read: an action may write the story (glues)
        repo._save_story(db,story.model_copy(update={'revision':expected_revision+1}))
    # VALID-LINKS rule (г): the panel asks the author whether to uncheck these scenes; the change alone moves no link.
    return {**locations_view(repo,story_id),'dependent_scene_ids':[id for id in after if after[id]!=before.get(id)]}


def _shown_by_scene(db, story_id: str) -> dict[str,tuple]:
    """{scene id: («ЛОКАЦІЇ СЦЕНИ» rows, location neighbourhood)} of the active scenes in book order: a scene depends on
    a location change when what its context shows changes (its own card, a merge target or an ancestor's description)
    or the neighbourhood that selects nearby memory changes (a card merged into one of its places). Only scenes with a
    brief: without one Z1 and Z2 are missing and the invalidation would write nothing."""
    from ..domain import Scene
    cards=load_locations(db,story_id)
    scenes=[Scene.model_validate_json(r[0]) for r in db.execute(
        'SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id',(story_id,))]
    return {scene.id:(shown_locations(cards,scene.location_ids),sorted(scene_neighbourhood(cards,scene.location_ids)))
            for scene in scenes if not scene.trashed_at and scene.heads.get('brief')}
