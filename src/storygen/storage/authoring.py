from ..domain import RevisionConflict, Scene, Story


def rename_story(repo,story_id,title,expected_revision):
    title=title.strip()
    if not 1<=len(title)<=300:
        raise ValueError('Назва повинна містити від 1 до 300 символів')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:
            raise RevisionConflict('Твір уже змінено. Скасуйте перейменування й відкрийте його знову.')
        if story.title!=title:
            story.title=title
            story.revision+=1
            repo._save_story(db,story)
    return story


def unchanged_scene_text(repo,scene_id,head,text,expected_revision):
    """Reuse only the selected identical material; never rebase or accept it."""
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        scene=repo._active_scene(db,scene_id)
        repo._active_story(db,scene.story_id)
        id=scene.heads.get(head)
        if not id:return None
        from ..domain import VersionRef
        ref=repo._get(db,'versions',id,VersionRef)
        if ref.scene_id!=scene.id or ref.story_id!=scene.story_id or not ref.complete:
            return None
        if repo.files.read(ref.relative_path,ref.sha256)!=text.encode('utf-8'):
            return None
        if scene.revision!=expected_revision:
            raise RevisionConflict('Сцену вже змінено. Оновіть матеріал перед збереженням.')
        from .context_view import ContextView
        return scene,ContextView(repo,db,scene.story_id).get_version(id)


def update_scene_plan(repo,scene_id: str,text: str,expected_revision: int) -> Scene:
    unchanged=unchanged_scene_text(repo,scene_id,'plan',text,expected_revision)
    if unchanged:return unchanged[0]
    scene=repo.get_scene(scene_id)
    version=repo.save_version(scene.story_id,scene.id,"scene_plan",text,[])
    with repo.db.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        current=repo._active_scene(db,scene_id)
        if current.revision!=expected_revision:
            raise RevisionConflict("Сцену змінено в іншій вкладці")
        previous=current.heads.get('plan')
        from .scene_metadata import apply_description
        apply_description(repo,db,current,text)
        current.beats=text
        current.heads["plan"]=version.id
        current.head_revisions["plan"]=current.head_revisions.get("plan",0)+1
        current.revision+=1
        repo._save_scene(db,current)
        if previous:
            from .invalidation import invalidate_in_transaction
            invalidate_in_transaction(repo,db,[previous])
        repo._touch_story(db,current.story_id)
    return current


def update_scene_metadata(repo,scene_id: str,changes: dict,expected_revision: int) -> Scene:
    allowed={"title","target_words","character_ids"}
    if set(changes)-allowed:
        raise ValueError("Непідтримувані поля сцени")
    with repo.db.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        scene=repo._active_scene(db,scene_id)
        if scene.revision!=expected_revision:
            raise RevisionConflict("Сцену вже змінено")
        candidate=Scene.model_validate({**scene.model_dump(),**changes})
        if candidate==scene:return scene
        scene=candidate.model_copy(update={'revision':scene.revision+1})
        repo._save_scene(db,scene)
        from .invalidation import invalidate_in_transaction
        invalidate_in_transaction(repo,db,list(scene.heads.values()))
        repo._touch_story(db,scene.story_id)
    return scene


def reorder_scenes(repo,story_id: str,scene_ids: list[str],expected_revision: int) -> Story:
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
        from .invalidation import invalidate_in_transaction
        invalidate_in_transaction(repo,db,[head for scene in scenes.values() for head in scene.heads.values()])
        return repo._touch_story(db,story_id)

from ..domain import VersionRef, SceneCreate, new_id, now
import json

def _idle(repo,db,story_id):
    if db.execute("SELECT 1 FROM runs WHERE story_id=? AND state NOT IN ('completed','failed','cancelled') LIMIT 1",(story_id,)).fetchone():
        raise ValueError('Спершу завершіть або скасуйте всі запуски цього твору')

def _revision(item,expected):
    if item.revision!=expected:
        raise RevisionConflict('Матеріал уже змінено. Оновіть сторінку')

def set_story_trashed(repo,story_id,expected_revision,restore):
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

def _invalidate_later(repo,db,scenes):
    from .invalidation import invalidate_in_transaction
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

def set_scene_trashed(repo,story_id,scene_id,expected_revision,restore):
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
            from .invalidation import invalidate_in_transaction
            invalidate_in_transaction(repo,db,list(scene.heads.values()))
        repo._touch_story(db,story_id)
        return repo._get(db,'scenes',scene_id,Scene)



def _material(repo, db, story_id, version_id, kind):
    ref = repo._get(db, 'versions', version_id, VersionRef)
    if ref.story_id != story_id or ref.kind != kind or not ref.complete:
        raise ValueError('Матеріал має інший тип, власника або не завершений')
    return ref


def publish_story_material(repo, story_id, field, version_id, expected_revision):
    kinds = {'style_version_id': 'style','characters_version_id':'character_cards'}
    if field not in kinds:
        raise ValueError('Непідтримуваний матеріал твору')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        _revision(story, expected_revision)
        _material(repo, db, story_id, version_id, kinds[field])
        previous = getattr(story, field)
        setattr(story, field, version_id)
        story.revision += 1
        repo._save_story(db, story)
        from .invalidation import invalidate_in_transaction, invalidate_story_materials
        if previous:
            invalidate_in_transaction(repo, db, [previous])
        else:
            invalidate_story_materials(repo, db, story_id)
        if field=='characters_version_id':
            from .scene_metadata import sync_story_cast
            sync_story_cast(repo,db,story_id)
        return story


def publish_blueprint(repo, story_id, canon_id, character_cards_id, scenes, expected_revision):
    from .invalidation import invalidate_in_transaction, invalidate_story_materials
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story = repo._active_story(db, story_id)
        _revision(story, expected_revision)
        _material(repo, db, story_id, canon_id, 'canon')
        _material(repo, db, story_id, character_cards_id, 'character_cards')
        planned = [(SceneCreate.model_validate(data), _material(repo, db, story_id, ref.id, 'scene_plan')) for data, ref in scenes]
        if planned and db.execute('SELECT 1 FROM scenes WHERE story_id=?', (story_id,)).fetchone():
            raise ValueError('Наявні сцени не можна замінити пропозицією')
        for _, ref in planned:
            if ref.scene_id is not None:
                raise ValueError('План уже належить сцені')
        previous = [id for id in [story.canon_version_id, story.characters_version_id] if id]
        story.canon_version_id = canon_id
        story.characters_version_id = character_cards_id
        story.revision += 1
        repo._save_story(db, story)
        invalidate_in_transaction(repo, db, previous)
        invalidate_story_materials(repo, db, story_id)
        for position, (data, plan) in enumerate(planned):
            scene = Scene(id=new_id(), story_id=story_id, **{**data.model_dump(), 'position': position})
            from .scene_metadata import apply_description
            apply_description(repo,db,scene,scene.beats)
            scene.heads['plan'] = plan.id
            scene.head_revisions['plan'] = 1
            db.execute('INSERT INTO scenes VALUES(?,?,?,?)', (scene.id, story_id, position, scene.model_dump_json()))
            plan.scene_id = scene.id
            db.execute('UPDATE versions SET scene_id=?,payload=? WHERE id=?', (scene.id, plan.model_dump_json(), plan.id))
        from .scene_metadata import sync_story_cast
        sync_story_cast(repo,db,story_id)
        return story


def register_source(repo, story_id, metadata):
    from .invalidation import invalidate_in_transaction, invalidate_story_materials
    if metadata['kind'] not in {'source_plan', 'source_characters'}:
        raise ValueError('Невідомий тип джерела')
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        repo._active_story(db, story_id)
        _material(repo, db, story_id, metadata['version_id'], metadata['kind'])
        previous = repo._active_source(db, story_id, metadata['kind'])
        db.execute('INSERT INTO source_files VALUES(?,?,?)', (metadata['id'], story_id, json.dumps(metadata, ensure_ascii=False)))
        repo._touch_story(db, story_id)
        if previous:
            invalidate_in_transaction(repo, db, [previous.id])
        elif metadata['kind'] == 'source_characters':
            invalidate_story_materials(repo, db, story_id)
