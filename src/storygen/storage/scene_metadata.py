"""Scene metadata derived from author plans within storage transactions."""
from ..scene_description import parse_scene_description,resolve_participants
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
