from ..domain import RevisionConflict, Scene, Story
from ..storage.repository import Repository


def update_scene_plan(repo: Repository,scene_id: str,text: str,expected_revision: int) -> Scene:
    scene=repo.get_scene(scene_id)
    version=repo.save_version(scene.story_id,scene.id,"scene_plan",text,[])
    with repo.db.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        current=repo._active_scene(db,scene_id)
        if current.revision!=expected_revision:
            raise RevisionConflict("Сцену змінено в іншій вкладці")
        previous=current.heads.get('plan')
        current.beats=text
        current.heads["plan"]=version.id
        current.revision+=1
        repo._save_scene(db,current)
        if previous:
            from ..generation.dependencies import invalidate_in_transaction
            invalidate_in_transaction(repo,db,[previous])
        repo._touch_story(db,current.story_id)
    return current


def update_scene(repo: Repository,scene_id: str,changes: dict,expected_revision: int) -> Scene:
    allowed={"title","target_words","character_ids"}
    if set(changes)-allowed:
        raise ValueError("Непідтримувані поля сцени")
    with repo.db.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        scene=repo._active_scene(db,scene_id)
        if scene.revision!=expected_revision:
            raise RevisionConflict("Сцену вже змінено")
        scene=Scene.model_validate({**scene.model_dump(),**changes,"revision":scene.revision+1})
        repo._save_scene(db,scene)
        from ..generation.dependencies import invalidate_in_transaction
        invalidate_in_transaction(repo,db,list(scene.heads.values()))
        repo._touch_story(db,scene.story_id)
    return scene


def reorder_scenes(repo: Repository,story_id: str,scene_ids: list[str],expected_revision: int) -> Story:
    with repo.db.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:
            raise RevisionConflict("Порядок або матеріали твору вже змінено")
        rows=db.execute("SELECT payload FROM scenes WHERE story_id=? ORDER BY position",(story_id,)).fetchall()
        all_scenes=[Scene.model_validate_json(row[0]) for row in rows]
        archived=[s for s in all_scenes if s.trashed_at]
        scenes={s.id:s for s in all_scenes if not s.trashed_at}
        if len(scene_ids)!=len(scenes) or set(scene_ids)!=set(scenes):
            raise ValueError("Потрібні всі сцени цього твору рівно один раз")
        for scene in scenes.values():
            scene.revision+=1
            scene.needs_review=True
        repo._save_scene_order(db,[scenes[id] for id in scene_ids]+archived)
        from ..generation.dependencies import invalidate_in_transaction
        invalidate_in_transaction(repo,db,[head for scene in scenes.values() for head in scene.heads.values()])
        return repo._touch_story(db,story_id)
