"""Scene metadata derived from author plans within storage transactions."""
from ..scene_description import parse_scene_description,resolve_participants,explicit_scene_number
from ..characters.models import load_characters
from ..domain import Story,Scene,VersionRef


def story_cards(repo,db,story_id):
    story=repo._get(db,'stories',story_id,Story)
    if not story.characters_version_id:return []
    ref=repo._get(db,'versions',story.characters_version_id,VersionRef)
    return load_characters(repo.files.read(ref.relative_path,ref.sha256).decode('utf-8'))


def apply_description(repo,db,scene,text,*,include_title=True,cards=None):
    previous=(scene.title,scene.character_ids.copy())
    parsed=parse_scene_description(text)
    if include_title:
        creating=not db.execute('SELECT 1 FROM scenes WHERE id=?',(scene.id,)).fetchone()
        number=explicit_scene_number(text)
        if creating and scene.author_scene_number is not None:
            if number is not None and number!=scene.author_scene_number:raise ValueError('Номер сцени суперечить заголовку плану')
            number=scene.author_scene_number
        if number is not None and (number!=scene.author_scene_number or creating):
            for row in db.execute('SELECT payload FROM scenes WHERE story_id=?',(scene.story_id,)):
                other=Scene.model_validate_json(row[0])
                if other.id!=scene.id and not other.trashed_at and other.author_scene_number==number:
                    raise ValueError(f'Номер сцени {number} вже використано')
        scene.author_scene_number=number
    if include_title and parsed.title:scene.title=parsed.title
    if parsed.participants is not None:
        if cards is None:cards=story_cards(repo,db,scene.story_id)
        scene.character_ids=resolve_participants(parsed.participants,cards)[0]
    if previous!=(scene.title,scene.character_ids):
        roots=[id for head,id in getattr(scene,'heads',{}).items() if head!='plan']
        for id in roots:
            ref=repo._get(db,'versions',id,VersionRef)
            if ref.dependency_snapshot is None and ref.kind in {'brief','draft','edited','memory','evaluation'}:
                ref.stale=True
                db.execute('UPDATE versions SET payload=? WHERE id=?',(ref.model_dump_json(),ref.id))
        if roots:
            scene.needs_review=True
            from .invalidation import invalidate_in_transaction
            invalidate_in_transaction(repo,db,roots)


def cast_names(ids,cards):
    """Plan-line form of a cast: the card name where it resolves back to the same card, otherwise the exact ID."""
    names={card.id:card.name for card in cards}
    def written(id):
        name=names.get(id)
        return name if name and resolve_participants(parse_scene_description('Персонажі: '+name).participants,cards)[0]==[id] else id
    return ', '.join(written(id) for id in ids)


def templated_plan(repo,db,story,active,position,data):
    """SCENE-PLAN-TEMPLATE: the plan of a new scene from the closest active scene before its position."""
    from ..scene_plan_template import next_scene_plan,plan_fields
    previous=active[position-1] if position else None
    fields=plan_fields(previous.beats) if previous else {}
    ids=data.character_ids or ([] if 'cast' in fields or not previous else previous.character_ids)  # 'cast' holds only a non-empty line value
    if ids:fields['cast']=cast_names(ids,story_cards(repo,db,story.id))
    number=data.author_scene_number
    if number is None:
        taken={scene.author_scene_number for scene in active}
        # An unnumbered previous scene counts by its place in reading order; a taken number is never reused.
        number=(position if previous is None or previous.author_scene_number is None else previous.author_scene_number)+1
        while number in taken:number+=1
    return next_scene_plan(story.language,number,data.title,fields)


def sync_story_cast(repo,db,story_id):
    cards=story_cards(repo,db,story_id)
    for row in db.execute('SELECT payload FROM scenes WHERE story_id=?',(story_id,)).fetchall():
        scene=Scene.model_validate_json(row[0])
        if scene.trashed_at:continue
        before=scene.character_ids.copy()
        apply_description(repo,db,scene,scene.beats,include_title=False,cards=cards)
        if scene.character_ids!=before:
            scene.revision+=1
            repo._save_scene(db,scene)
