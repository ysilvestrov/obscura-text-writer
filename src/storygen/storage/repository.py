import hashlib
import json
from pathlib import Path

from ..domain import RevisionConflict, Scene, SceneCreate, Story, StoryCreate, VersionRef, StageAttempt, new_id
from .database import Database
from .files import FileStore


class Repository:
    def __init__(self,data_dir: Path):
        self.root=data_dir.resolve()
        self.db=Database(self.root/"storygen.sqlite3")
        self.files=FileStore(self.root)

    def _get(self,db,table,id,model):
        row=db.execute(f"SELECT payload FROM {table} WHERE id=?",(id,)).fetchone()
        if row is None:
            raise KeyError("Матеріал не знайдено")
        return model.model_validate_json(row[0])

    def _active_story(self,db,id: str) -> Story:
        story=self._get(db,"stories",id,Story)
        if story.trashed_at:
            raise KeyError("Твір у кошику")
        return story

    def _active_scene(self,db,id: str) -> Scene:
        scene=self._get(db,"scenes",id,Scene)
        self._active_story(db,scene.story_id)
        if scene.trashed_at:
            raise KeyError("Сцена у кошику")
        return scene

    def get_story(self,id: str,include_trashed: bool=False) -> Story:
        with self.db.connection() as db:
            return self._get(db,"stories",id,Story) if include_trashed else self._active_story(db,id)

    def get_scene(self,id: str,include_trashed: bool=False) -> Scene:
        with self.db.connection() as db:
            return self._get(db,"scenes",id,Scene) if include_trashed else self._active_scene(db,id)

    def get_version(self,id: str) -> VersionRef:
        with self.db.connection() as db:
            ref=self._get(db,"versions",id,VersionRef)
            self._active_story(db,ref.story_id)
            if ref.scene_id:self._active_scene(db,ref.scene_id)
            return ref

    def list_stories(self,include_trashed: bool=False) -> list[Story]:
        with self.db.connection() as db:
            stories=[Story.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM stories ORDER BY rowid DESC")]
            return stories if include_trashed else [s for s in stories if not s.trashed_at]

    def _active_source(self,db,story_id,kind):
        for row in db.execute('SELECT payload FROM source_files WHERE story_id=? ORDER BY rowid DESC',(story_id,)):
            metadata=json.loads(row[0])
            if metadata['kind']==kind:
                return self._get(db,'versions',metadata['version_id'],VersionRef)
        return None

    def active_source(self,story_id,kind):
        with self.db.connection() as db:
            self._active_story(db,story_id)
            return self._active_source(db,story_id,kind)

    def list_scenes(self,story_id: str,include_trashed: bool=False) -> list[Scene]:
        with self.db.connection() as db:
            self._active_story(db,story_id)
            scenes=[Scene.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id",(story_id,))]
            return scenes if include_trashed else [s for s in scenes if not s.trashed_at]

    def list_versions(self,story_id: str,scene_id: str | None = None,kind: str | None = None) -> list[VersionRef]:
        with self.db.connection() as db:
            self._active_story(db,story_id)
            if scene_id:self._active_scene(db,scene_id)
            rows=db.execute("SELECT payload FROM versions WHERE story_id=? ORDER BY rowid",(story_id,))
            versions=[VersionRef.model_validate_json(r[0]) for r in rows]
        active_ids={s.id for s in self.list_scenes(story_id)}
        return [v for v in versions if (v.scene_id is None or v.scene_id in active_ids) and (scene_id is None or v.scene_id==scene_id) and (kind is None or v.kind==kind)]

    def _save_story(self,db,story):
        db.execute("UPDATE stories SET payload=? WHERE id=?",(story.model_dump_json(),story.id))

    def _save_scene(self,db,scene):
        db.execute("UPDATE scenes SET position=?,payload=? WHERE id=?",(scene.position,scene.model_dump_json(),scene.id))

    def _save_scene_order(self,db,scenes):
        for index,scene in enumerate(scenes):
            db.execute("UPDATE scenes SET position=? WHERE id=?",(-index-1,scene.id))
        for index,scene in enumerate(scenes):
            if scene.position!=index:
                scene.position=index
                scene.revision+=1
            self._save_scene(db,scene)

    def _touch_story(self,db,story_id):
        story=self._get(db,"stories",story_id,Story)
        story.revision+=1
        self._save_story(db,story)
        return story

    def create_story(self,data: StoryCreate) -> Story:
        story=Story(id=new_id(),**data.model_dump())
        with self.db.connection() as db:
            db.execute("INSERT INTO stories VALUES(?,?)",(story.id,story.model_dump_json()))
        return story

    def create_scene(self,story_id: str,data: SceneCreate) -> Scene:
        with self.db.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active_story(db,story_id)
            scenes=[Scene.model_validate_json(r[0]) for r in db.execute("SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id",(story_id,))]
            active=[s for s in scenes if not s.trashed_at]
            archived=[s for s in scenes if s.trashed_at]
            position=len(active) if data.position is None else min(data.position,len(active))
            scene=Scene(id=new_id(),story_id=story_id,**{**data.model_dump(),"position":len(scenes)})
            db.execute("INSERT INTO scenes VALUES(?,?,?,?)",(scene.id,story_id,scene.position,scene.model_dump_json()))
            active.insert(position,scene)
            self._save_scene_order(db,active+archived)
            self._touch_story(db,story_id)
        return scene

    def save_version(self,story_id: str,scene_id: str | None,kind: str,text: str,input_refs: list[str],source_run_id: str | None = None) -> VersionRef:
        self.get_story(story_id)
        if scene_id and self.get_scene(scene_id).story_id != story_id:
            raise ValueError("Сцена належить іншому твору")
        if any(self.get_version(id).story_id != story_id for id in input_refs):
            raise ValueError("Джерела належать іншому твору")
        format="json" if kind in {"character_cards","style","memory","evaluation","brief"} else "text"
        id=new_id()
        data=text.encode("utf-8")
        version=VersionRef(id=id,story_id=story_id,scene_id=scene_id,kind=kind,format=format,sha256=hashlib.sha256(data).hexdigest(),
            relative_path=f"stories/{story_id}/versions/{id}.{'json' if format=='json' else 'txt'}",input_refs=input_refs,source_run_id=source_run_id)
        self.files.write(version.relative_path,data)
        with self.db.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._active_story(db,story_id)
            if scene_id:self._active_scene(db,scene_id)
            db.execute("INSERT INTO versions VALUES(?,?,?,?,?)",(id,story_id,scene_id,kind,version.model_dump_json()))
            db.executemany("INSERT INTO dependency_edges VALUES(?,?)",[(source,id) for source in set(input_refs)])
        return version

    def read_text(self,version_id: str) -> str:
        version=self.get_version(version_id)
        return self.files.read(version.relative_path,version.sha256).decode("utf-8")

    def set_head(self,scene_id: str,head: str,version_id: str,expected_revision: int) -> Scene:
        version=self.get_version(version_id)
        allowed={"brief":{"brief"},"draft":{"draft"},"prose":{"edited","manual"},"memory":{"memory"},"plan":{"scene_plan"}}
        if head not in allowed or version.kind not in allowed[head] or version.scene_id != scene_id or not version.complete or version.stale:
            raise ValueError("Ця версія не може стати поточною")
        self.read_text(version_id)
        with self.db.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            version=self._get(db,'versions',version_id,VersionRef)
            if version.stale or not version.complete:
                raise ValueError('Версія застаріла або незавершена')
            scene=self._active_scene(db,scene_id)
            if scene.revision != expected_revision:
                raise RevisionConflict("Сцену вже змінено. Ваш текст збережіть окремою версією.")
            previous=scene.heads.get(head)
            scene.heads[head]=version_id
            scene.revision+=1
            self._save_scene(db,scene)
            if previous and previous!=version_id:
                from ..generation.dependencies import invalidate_in_transaction
                invalidate_in_transaction(self,db,[previous],exclude=[version_id])
            if head=='prose':
                scene.needs_review=False
                self._save_scene(db,scene)
            self._touch_story(db,scene.story_id)
        return scene

    def save_attempt(self,attempt: StageAttempt) -> StageAttempt:
        with self.db.connection() as db:
            db.execute('INSERT INTO stage_attempts VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state,payload=excluded.payload',
                (attempt.id,attempt.run_id,attempt.story_id,attempt.scene_id,attempt.state,attempt.model_dump_json()))
        return attempt

    def get_attempt(self,id: str) -> StageAttempt:
        with self.db.connection() as db:
            return self._get(db,'stage_attempts',id,StageAttempt)

    def list_attempts(self,story_id: str,run_id: str | None = None) -> list[StageAttempt]:
        with self.db.connection() as db:
            attempts=[StageAttempt.model_validate_json(row[0]) for row in db.execute('SELECT payload FROM stage_attempts WHERE story_id=? ORDER BY rowid',(story_id,))]
        return [a for a in attempts if run_id is None or a.run_id==run_id]

    def commit_stage_result(self,attempt_id: str,result_ref: VersionRef,expected_revision: int | None) -> StageAttempt:
        self.read_text(result_ref.id)
        with self.db.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            attempt=self._get(db,'stage_attempts',attempt_id,StageAttempt)
            if attempt.state!='running' or result_ref.story_id!=attempt.story_id or result_ref.scene_id!=attempt.scene_id:
                raise ValueError('Спроба або результат не відповідають етапу')
            story=self._active_story(db,attempt.story_id)
            changed=story.revision!=attempt.context['story_revision']
            for source_id in result_ref.input_refs:
                source=self._get(db,'versions',source_id,VersionRef)
                accepted_stale=source_id in attempt.context.get('accepted_stale_prose_ids',[]) and source.kind in {'edited','manual'}
                changed=changed or (source.stale and not accepted_stale)
            attempt.result_version_id=result_ref.id
            if attempt.scene_id:
                scene=self._active_scene(db,attempt.scene_id)
                changed=changed or scene.revision!=expected_revision
                if not changed:
                    head={'brief':'brief','draft':'draft','edit':'prose','memory':'memory'}[attempt.stage]
                    previous=scene.heads.get(head)
                    scene.heads[head]=result_ref.id
                    scene.revision+=1
                    self._save_scene(db,scene)
                    if previous and previous!=result_ref.id:
                        from ..generation.dependencies import invalidate_in_transaction
                        invalidate_in_transaction(self,db,[previous],exclude=[result_ref.id])
                    if attempt.stage=='edit':
                        scene.needs_review=False
                        self._save_scene(db,scene)
                    self._touch_story(db,scene.story_id)
            attempt.state='alternative' if changed else 'completed'
            db.execute('UPDATE stage_attempts SET state=?,payload=? WHERE id=?',(attempt.state,attempt.model_dump_json(),attempt.id))
        return attempt
