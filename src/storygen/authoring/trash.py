from ..domain import RevisionConflict, Scene, Story, VersionRef, now


def _idle(repo,db,story_id):
    if db.execute("SELECT 1 FROM runs WHERE story_id=? AND state NOT IN ('completed','failed','cancelled') LIMIT 1",(story_id,)).fetchone():
        raise ValueError('Спершу завершіть або скасуйте всі запуски цього твору')


def _revision(item,expected):
    if item.revision!=expected:
        raise RevisionConflict('Матеріал уже змінено. Оновіть сторінку')


def _story_state(repo,story_id,expected_revision,restore):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._get(db,'stories',story_id,Story)
        _revision(story,expected_revision)
        if bool(story.trashed_at)!=restore:
            raise ValueError('Твір уже відновлено' if restore else 'Твір уже в кошику')
        _idle(repo,db,story_id)
        story.trashed_at=None if restore else now()
        story.revision+=1
        repo._save_story(db,story)
        return story


def trash_story(repo,story_id,expected_revision):
    return _story_state(repo,story_id,expected_revision,False)


def restore_story(repo,story_id,expected_revision):
    return _story_state(repo,story_id,expected_revision,True)


def _invalidate_later(repo,db,scenes):
    from ..generation.dependencies import invalidate_in_transaction
    ids={scene.id for scene in scenes}
    roots=[]
    for row in db.execute('SELECT payload FROM versions WHERE story_id=?',(scenes[0].story_id,)) if scenes else []:
        ref=VersionRef.model_validate_json(row[0])
        if ref.scene_id in ids and ref.kind in {'brief','draft','edited','manual','memory','evaluation'}:
            ref.stale=True
            roots.append(ref.id)
            db.execute('UPDATE versions SET payload=? WHERE id=?',(ref.model_dump_json(),ref.id))
    invalidate_in_transaction(repo,db,roots)
    for scene in scenes:
        current=repo._get(db,'scenes',scene.id,Scene)
        current.needs_review=True
        current.revision+=1
        repo._save_scene(db,current)


def _scene_state(repo,story_id,scene_id,expected_revision,restore):
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        repo._active_story(db,story_id)
        scene=repo._get(db,'scenes',scene_id,Scene)
        if scene.story_id!=story_id:
            raise ValueError('Сцена належить іншому твору')
        _revision(scene,expected_revision)
        if bool(scene.trashed_at)!=restore:
            raise ValueError('Сцену вже відновлено' if restore else 'Сцена вже в кошику')
        _idle(repo,db,story_id)
        all_scenes=[Scene.model_validate_json(r[0]) for r in db.execute('SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id',(story_id,))]
        active=[s for s in all_scenes if not s.trashed_at and s.id!=scene_id]
        archived=[s for s in all_scenes if s.trashed_at and s.id!=scene_id]
        index=min(scene.trashed_position if restore and scene.trashed_position is not None else scene.position,len(active))
        if restore:
            scene.trashed_at=None
            scene.trashed_position=None
            active.insert(index,scene)
        else:
            scene.trashed_at=now()
            scene.trashed_position=scene.position
            archived.append(scene)
        scene.revision+=1
        repo._save_scene(db,scene)
        repo._save_scene_order(db,active+archived)
        # A changed scene boundary invalidates subsequent context even without explicit dependency edges.
        _invalidate_later(repo,db,active[index:])
        if not restore:
            from ..generation.dependencies import invalidate_in_transaction
            invalidate_in_transaction(repo,db,list(scene.heads.values()))
        repo._touch_story(db,story_id)
        return repo._get(db,'scenes',scene_id,Scene)


def trash_scene(repo,story_id,scene_id,expected_revision):
    return _scene_state(repo,story_id,scene_id,expected_revision,False)


def restore_scene(repo,story_id,scene_id,expected_revision):
    return _scene_state(repo,story_id,scene_id,expected_revision,True)
