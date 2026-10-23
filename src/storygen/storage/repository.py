import hashlib
import json
from pathlib import Path

from ..domain import RevisionConflict, Scene, SceneCreate, Story, StoryCreate, VersionRef, StageAttempt, new_id
from .database import Database
from .files import FileStore


class Repository:
    def unchanged_scene_text(self,scene_id,head,text,expected_revision):
        from .authoring import unchanged_scene_text
        return unchanged_scene_text(self,scene_id,head,text,expected_revision)

    def publication(self, action, **data):
        from .publication_store import operation
        return operation(self, action, **data)

    def publication_snapshot(self, story_id):
        from .publication_store import publication_snapshot
        return publication_snapshot(self, story_id)

    def role_profiles(self,action,**data):
        from .role_profile_store import operation
        return operation(self,action,**data)

    def commit_copyedit_selection(self,attempt_id,result_ref,indices,expected_revision,fingerprint,warnings):
        from .copyedit_store import commit_copyedit_selection
        return commit_copyedit_selection(self,attempt_id,result_ref,indices,expected_revision,fingerprint,warnings)

    def update_scene_plan(self, scene_id, text, expected_revision):
        from .authoring import update_scene_plan
        return update_scene_plan(self, scene_id, text, expected_revision)

    def update_scene_metadata(self, scene_id, changes, expected_revision):
        from .authoring import update_scene_metadata
        return update_scene_metadata(self, scene_id, changes, expected_revision)

    def reorder_scenes(self, story_id, scene_ids, expected_revision):
        from .authoring import reorder_scenes
        return reorder_scenes(self, story_id, scene_ids, expected_revision)

    def set_story_trashed(self, story_id, expected_revision, restore):
        from .authoring import set_story_trashed
        return set_story_trashed(self, story_id, expected_revision, restore)

    def set_scene_trashed(self, story_id, scene_id, expected_revision, restore):
        from .authoring import set_scene_trashed
        return set_scene_trashed(self, story_id, scene_id, expected_revision, restore)

    def publish_story_material(self, story_id, field, version_id, expected_revision):
        from .authoring import publish_story_material
        return publish_story_material(self, story_id, field, version_id, expected_revision)

    def publish_blueprint(self, story_id, canon_id, character_cards_id, scenes, expected_revision):
        from .authoring import publish_blueprint
        return publish_blueprint(self, story_id, canon_id, character_cards_id, scenes, expected_revision)

    def register_source(self, story_id, metadata):
        from .authoring import register_source
        return register_source(self, story_id, metadata)

    def read_role_settings(self, story_id):
        from .settings_store import read_role_settings
        return read_role_settings(self, story_id)

    def write_role_settings(self, story_id, updates, expected_revision):
        from .settings_store import write_role_settings
        return write_role_settings(self, story_id, updates, expected_revision)

    def token_records(self, kind):
        from .token_store import records
        return records(self, kind)

    def billing(self, action, **data):
        from .billing_store import operation
        return operation(self, action, **data)

    def record_token_observation(self, item):
        from .token_store import record
        return record(self, item)

    def token_profile_action(self, identity, action):
        from .token_store import profile_action
        return profile_action(self, identity, action)

    def get_run(self, id):
        from .run_store import get_run
        return get_run(self, id)

    def list_runs(self, story_id=None):
        from .run_store import list_runs
        return list_runs(self, story_id)

    def save_run(self, run):
        from .run_store import save_run
        return save_run(self, run)

    def requeue_run(self, run):
        from .run_store import requeue_run
        return requeue_run(self, run)

    def find_run_by_request_id(self, request_id):
        from .run_store import find_run_by_request_id
        return find_run_by_request_id(self, request_id)

    def enqueue_run(self, candidate):
        from .run_store import enqueue_run
        return enqueue_run(self, candidate)

    def append_run_event(self, run_id, type, data):
        from .run_store import append_run_event
        return append_run_event(self, run_id, type, data)

    def list_run_events(self, run_id, after_seq=0):
        from .run_store import list_run_events
        return list_run_events(self, run_id, after_seq)

    def recover_running_attempts(self):
        from .run_store import recover_running_attempts
        return recover_running_attempts(self)

    def read_evaluator_settings(self, story_id):
        from .settings_store import read_evaluator_settings
        return read_evaluator_settings(self, story_id)

    def write_evaluator_settings(self, story_id, payload):
        from .settings_store import write_evaluator_settings
        return write_evaluator_settings(self, story_id, payload)

    def read_calibration(self, id):
        from .settings_store import read_calibration
        return read_calibration(self, id)

    def register_calibration(self, id, payload):
        from .settings_store import register_calibration
        return register_calibration(self, id, payload)

    def read_refusal_block(self, story_id, identity_hash):
        from .settings_store import read_refusal_block
        return read_refusal_block(self, story_id, identity_hash)

    def record_refusal_block(self, story_id, identity_hash, payload):
        from .settings_store import record_refusal_block
        return record_refusal_block(self, story_id, identity_hash, payload)

    def publish_evaluation(self, ref_id, expected_story_revision, input_refs, snapshot=None):
        from .context_view import ContextView
        from .snapshots import compare_snapshot
        with self.db.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            ref = self._get(db, 'versions', ref_id, VersionRef)
            story = self._active_story(db, ref.story_id)
            if ref.kind != 'evaluation' or ref.input_refs != input_refs:
                raise ValueError('Невідповідні джерела звіту')
            view = ContextView(self, db, story.id)
            if snapshot is not None:
                from ..dependency_models import DependencySnapshot
                snapshot = DependencySnapshot.model_validate(snapshot)
                if snapshot.scope != 'evaluation' or set(snapshot.refs) != set(input_refs):
                    raise ValueError('Невідповідний знімок оцінювання')
                ref.dependency_snapshot = snapshot
                ref.stale = bool(compare_snapshot(view, snapshot))
            else:
                inputs = [view.get_version(id) for id in input_refs]
                if any(v.story_id != story.id for v in inputs):
                    raise ValueError('Джерело іншого твору')
                ref.stale = ref.stale or any(v.stale for v in inputs) or story.revision != expected_story_revision
            db.execute('UPDATE versions SET payload=? WHERE id=?', (ref.model_dump_json(), ref.id))
            return ref

    def context_view(self, story_id):
        from .context_view import ContextView
        with self.db.connection() as db:
            db.execute('BEGIN')
            return ContextView(self, db, story_id)

    def preview_acceptance(self, scene_id, version_id):
        from .acceptance import preview_acceptance
        return preview_acceptance(self, scene_id, version_id)

    def accept_version(self, scene_id, version_id, expected_revision, preview_fingerprint, note=None):
        from .acceptance import accept_version
        return accept_version(self, scene_id, version_id, expected_revision, preview_fingerprint, note)

    def list_acceptances(self, story_id, version_id=None):
        from .acceptance import list_acceptances
        return list_acceptances(self, story_id, version_id)

    def continue_after_acceptance(self, id, version_id, expected_cursor, expected_scene_revision, acceptance_id=None):
        from .run_store import continue_after_acceptance
        return continue_after_acceptance(self,id,version_id,expected_cursor,expected_scene_revision,acceptance_id)

    def __init__(self,data_dir: Path):
        self.root=data_dir.resolve()
        if (self.root / '.restore-incomplete.json').exists():
            raise ValueError('Каталог містить незавершене відновлення. Відновіть резерв у новий каталог.')
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
            db.execute('BEGIN')
            if include_trashed:
                return self._get(db,'scenes',id,Scene)
            scene=self._active_scene(db,id)
            from .context_view import ContextView
            return ContextView(self,db,scene.story_id).effective_scene(id)

    def get_version(self,id: str) -> VersionRef:
        with self.db.connection() as db:
            db.execute('BEGIN')
            ref=self._get(db,'versions',id,VersionRef)
            self._active_story(db,ref.story_id)
            if ref.scene_id:self._active_scene(db,ref.scene_id)
            if ref.dependency_snapshot is None and ref.manual_projection_policy is None and not any(json.loads(r[0]).get('version_id')==ref.id for r in db.execute('SELECT payload FROM app_settings WHERE key LIKE ?',('acceptance:'+ref.story_id+':%',))):
                return ref
            from .context_view import ContextView
            return ContextView(self,db,ref.story_id).get_version(id)

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
        view=self.context_view(story_id)
        return [s.model_copy(deep=True) if s.trashed_at else view.effective_scene(s.id) for s in view.scenes.values() if include_trashed or not s.trashed_at]

    def export_snapshot(self, story_id: str) -> tuple[Story, list[tuple[Scene, VersionRef | None]]]:
        view=self.context_view(story_id)
        return view.get_story(story_id), [(view.effective_scene(s.id),view.get_version(s.heads['prose']) if s.heads.get('prose') else None) for s in view.list_scenes(story_id)]

    def list_versions(self,story_id: str,scene_id: str | None = None,kind: str | None = None) -> list[VersionRef]:
        view=self.context_view(story_id)
        if scene_id:view.get_scene(scene_id)
        active_ids={s.id for s in view.list_scenes(story_id)}
        return [view.get_version(v.id) for v in view.versions.values() if (v.scene_id is None or v.scene_id in active_ids) and (scene_id is None or v.scene_id==scene_id) and (kind is None or v.kind==kind)]

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
            from .scene_metadata import apply_description
            apply_description(self,db,scene,data.beats)
            db.execute("INSERT INTO scenes VALUES(?,?,?,?)",(scene.id,story_id,scene.position,scene.model_dump_json()))
            active.insert(position,scene)
            self._save_scene_order(db,active+archived)
            self._touch_story(db,story_id)
        return scene

    def save_version(self,story_id: str,scene_id: str | None,kind: str,text: str,input_refs: list[str],source_run_id: str | None = None,dependency_snapshot=None,prompt_contract=None,manual_projection_policy=None) -> VersionRef:
        if prompt_contract is not None and kind!='prompt':
            raise ValueError('Контракт дозволено лише для промпту')
        self.get_story(story_id)
        if scene_id and self.get_scene(scene_id).story_id != story_id:
            raise ValueError("Сцена належить іншому твору")
        source_view=self.context_view(story_id) if input_refs else None
        if any(source_view.get_version(id).story_id != story_id for id in input_refs):
            raise ValueError("Джерела належать іншому твору")
        format="json" if kind in {"character_cards","style","memory","evaluation","brief"} else "text"
        id=new_id()
        data=text.encode("utf-8")
        version=VersionRef(id=id,story_id=story_id,scene_id=scene_id,kind=kind,format=format,sha256=hashlib.sha256(data).hexdigest(),
            relative_path=f"stories/{story_id}/versions/{id}.{'json' if format=='json' else 'txt'}",input_refs=input_refs,source_run_id=source_run_id,dependency_snapshot=dependency_snapshot,prompt_contract=prompt_contract,manual_projection_policy=manual_projection_policy)
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
            from .context_view import ContextView
            view=ContextView(self,db,version.story_id)
            if view.get_version(version_id).stale or not version.complete:
                raise ValueError('Версія застаріла або незавершена')
            scene=self._active_scene(db,scene_id)
            if scene.revision != expected_revision:
                raise RevisionConflict("Сцену вже змінено. Ваш текст збережіть окремою версією.")
            previous=scene.heads.get(head)
            if previous==version_id:return scene
            scene.heads[head]=version_id
            scene.head_revisions[head]=scene.head_revisions.get(head,0)+1
            scene.revision+=1
            self._save_scene(db,scene)
            if previous and previous!=version_id:
                from .invalidation import invalidate_in_transaction
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
            from .context_view import ContextView
            from .snapshots import compare_snapshot
            from ..dependency_models import DependencySnapshot, TargetCAS
            snapshot_raw=attempt.context.get('dependency_snapshot')
            snapshot=DependencySnapshot.model_validate(snapshot_raw) if snapshot_raw is not None else None
            view=ContextView(self,db,story.id)
            if snapshot is not None:
                if set(snapshot.refs)!=set(result_ref.input_refs):
                    raise ValueError('Знімок не відповідає входам результату')
                result_ref.dependency_snapshot=snapshot
                changed=bool(compare_snapshot(view,snapshot))
                db.execute('UPDATE versions SET payload=? WHERE id=?',(result_ref.model_dump_json(),result_ref.id))
            else:
                changed=story.revision!=attempt.context['story_revision']
                for source_id in result_ref.input_refs:
                    source=self._get(db,'versions',source_id,VersionRef)
                    accepted_stale=source_id in attempt.context.get('accepted_stale_prose_ids',[]) and source.kind in {'edited','manual'}
                    changed=changed or (source.stale and not accepted_stale)
            attempt.result_version_id=result_ref.id
            if attempt.scene_id:
                scene=self._active_scene(db,attempt.scene_id)
                if snapshot is not None:
                    target=TargetCAS.model_validate(attempt.context.get('target_cas'))
                    head={'brief':'brief','draft':'draft','edit':'prose','memory':'memory'}[attempt.stage]
                    if target.scene_id!=scene.id or target.head!=head:
                        raise ValueError('Невідповідна ціль публікації')
                    changed=changed or scene.heads.get(head)!=target.version_id or scene.head_revisions.get(head,0)!=target.head_revision
                else:
                    changed=changed or scene.revision!=expected_revision
                if not changed:
                    head={'brief':'brief','draft':'draft','edit':'prose','memory':'memory'}[attempt.stage]
                    previous=scene.heads.get(head)
                    scene.heads[head]=result_ref.id
                    scene.head_revisions[head]=scene.head_revisions.get(head,0)+1
                    scene.revision+=1
                    self._save_scene(db,scene)
                    if previous and previous!=result_ref.id:
                        from .invalidation import invalidate_in_transaction
                        invalidate_in_transaction(self,db,[previous],exclude=[result_ref.id])
                    if attempt.stage=='edit':
                        scene.needs_review=False
                        self._save_scene(db,scene)
                        if attempt.context.get('copyedit_proposal'):
                            from ..copyediting import record_decision
                            record_decision(attempt,scene,list(range(len(attempt.context['copyedit_proposal']['proposal']['edits']))),result_ref.id,'auto',attempt.context.get('language_warnings',[]))
                    self._touch_story(db,scene.story_id)
            attempt.state='alternative' if changed else 'completed'
            db.execute('UPDATE stage_attempts SET state=?,payload=? WHERE id=?',(attempt.state,attempt.model_dump_json(),attempt.id))
        return attempt

    def invalidate_dependents(self, changed_version_ids: list[str]) -> list[str]:
        from .invalidation import invalidate_in_transaction
        with self.db.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            return invalidate_in_transaction(self, db, changed_version_ids)
