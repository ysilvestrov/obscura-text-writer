"""Dependency invalidation SQL; callers stay inside storage transactions."""
from ..domain import Scene, VersionRef


def invalidate_story_materials(repo,db,story_id):
    rows=db.execute('SELECT payload FROM versions WHERE story_id=?',(story_id,)).fetchall()
    for row in rows:
        ref=VersionRef.model_validate_json(row[0])
        if ref.kind in {'brief','draft','edited','memory','evaluation'}:
            ref.stale=True
            db.execute('UPDATE versions SET payload=? WHERE id=?',(ref.model_dump_json(),ref.id))
    for scene in [Scene.model_validate_json(row[0]) for row in db.execute('SELECT payload FROM scenes WHERE story_id=?',(story_id,))]:
        scene.needs_review=True
        repo._save_scene(db,scene)


def invalidate_in_transaction(repo,db,changed_version_ids: list[str],exclude=()) -> list[str]:
    queue=list(changed_version_ids)
    visited=set(queue)
    affected=[]
    while queue:
        source=queue.pop()
        for row in db.execute('SELECT target_id FROM dependency_edges WHERE source_id=?',(source,)):
            id=row[0]
            if id not in visited and id not in exclude:
                visited.add(id)
                queue.append(id)
                affected.append(id)
    scene_ids=set()
    for id in affected:
        ref=repo._get(db,'versions',id,VersionRef)
        ref.stale=True
        db.execute('UPDATE versions SET payload=? WHERE id=?',(ref.model_dump_json(),id))
        if ref.scene_id:
            scene_ids.add(ref.scene_id)
    for id in scene_ids:
        scene=repo._get(db,'scenes',id,Scene)
        scene.needs_review=True
        repo._save_scene(db,scene)
    return affected
