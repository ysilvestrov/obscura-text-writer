"""Atomic per-file publication; prepared immutable versions are never rewritten."""
import json
from ..domain import Scene,Story,VersionRef,new_id,RevisionConflict
from ..import_models import ImportPublication,ImportPublicationResult
from .authoring import _material
from .invalidation import invalidate_in_transaction,invalidate_story_materials


def source_files(db,story_id):
    result=[]
    for row in db.execute('SELECT payload FROM source_files WHERE story_id=?',(story_id,)):
        item=json.loads(row[0])
        version=db.execute('SELECT payload FROM versions WHERE id=?',(item['version_id'],)).fetchone()
        item['created_at']=json.loads(version[0]).get('created_at') if version else None
        result.append(item)
    return sorted(result,key=lambda r:(r['created_at'] or '',r['id']),reverse=True)


def publish_import(repo,story_id,expected_revision,publication):
    publication=ImportPublication.model_validate(publication)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        story=repo._active_story(db,story_id)
        if story.revision!=expected_revision:raise RevisionConflict('Матеріали вже змінено; імпорт файла не застосовано')
        metadata=dict(publication.metadata)
        if metadata.get('kind') not in {'source_plan','source_characters'}:raise ValueError('Невірний тип джерела')
        _material(repo,db,story_id,metadata['version_id'],metadata['kind'])
        repo.files.read(metadata['relative_path'],metadata['sha256'])
        protected={metadata['version_id']}
        changes=[]
        for kind,id in [('source_plan',publication.active_plan_version_id),('source_characters',publication.active_characters_version_id)]:
            if id:
                _material(repo,db,story_id,id,kind);protected.add(id)
                previous=repo._active_source(db,story_id,kind)
                if not previous or previous.id!=id:changes.append((kind,id,previous.id if previous else None))
        cards=publication.character_cards_version_id
        created_cards=0
        if cards:
            from ..characters.models import load_characters
            def card_ids(version_id):
                if not version_id:return set()
                ref=_material(repo,db,story_id,version_id,'character_cards')
                return {card.id for card in load_characters(repo.files.read(ref.relative_path,ref.sha256))}
            created_cards=len(card_ids(cards)-card_ids(story.characters_version_id))
            protected.add(cards)
        for item in publication.scenes:
            ref=_material(repo,db,story_id,item.plan_version_id,'scene_plan')
            if ref.scene_id is not None:raise ValueError('План нової сцени вже належить сцені')
            protected.add(ref.id)
        for id in protected:
            ref=repo._get(db,'versions',id,VersionRef)
            repo.files.read(ref.relative_path,ref.sha256)
        authored_plans={scene.heads.get('plan') for scene in [Scene.model_validate_json(r[0]) for r in db.execute('SELECT payload FROM scenes WHERE story_id=?',(story_id,))]}
        for kind,id,previous in changes:
            db.execute('INSERT INTO active_sources VALUES(?,?,?) ON CONFLICT(story_id,kind) DO UPDATE SET version_id=excluded.version_id',(story_id,kind,id))
            preserved=authored_plans|{story.canon_version_id,story.characters_version_id} if kind=='source_plan' else authored_plans
            if previous:invalidate_in_transaction(repo,db,[previous],exclude=protected,preserve=preserved)
        if cards:
            previous=story.characters_version_id
            story.characters_version_id=cards
            repo._save_story(db,story)
            if previous:invalidate_in_transaction(repo,db,[previous],exclude=protected,preserve=authored_plans)
            else:invalidate_story_materials(repo,db,story_id)
        scenes=[Scene.model_validate_json(r[0]) for r in db.execute('SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id',(story_id,))]
        active=[s for s in scenes if not s.trashed_at];archived=[s for s in scenes if s.trashed_at]
        created=[]
        from .scene_metadata import apply_description,sync_story_cast
        for item in publication.scenes:
            scene=Scene(id=new_id(),story_id=story_id,**{**item.data.model_dump(),'position':len(scenes)+len(created)})
            apply_description(repo,db,scene,scene.beats)
            scene.heads['plan']=item.plan_version_id;scene.head_revisions['plan']=1
            db.execute('INSERT INTO scenes VALUES(?,?,?,?)',(scene.id,story_id,scene.position,scene.model_dump_json()))
            ref=repo._get(db,'versions',item.plan_version_id,VersionRef)
            ref.scene_id=scene.id
            db.execute('UPDATE versions SET scene_id=?,payload=? WHERE id=?',(scene.id,ref.model_dump_json(),ref.id))
            active.append(scene);created.append(scene.id)
        if created:repo._save_scene_order(db,active+archived)
        if created:
            # BOOK-STRUCTURE: parts, arcs and bindings of the new scenes, in the same transaction as the scenes.
            from .book_structure import place_imported
            by_id={scene.id:scene for scene in active}
            placed=[(by_id[id],item.part_title,item.arc_title,item.part_index) for id,item in zip(created,publication.scenes)]
            repo._save_story(db,place_imported(repo._get(db,'stories',story_id,Story),active,placed,publication.structured))
        metadata.update(created_scene_count=len(created),created_character_count=created_cards)
        db.execute('INSERT INTO source_files VALUES(?,?,?)',(metadata['id'],story_id,json.dumps(metadata,ensure_ascii=False)))
        if cards:sync_story_cast(repo,db,story_id)
        story=repo._touch_story(db,story_id)
        return ImportPublicationResult(revision=story.revision,created_scene_ids=created)
