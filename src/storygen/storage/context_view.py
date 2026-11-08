"""A captured SQL read view; no mutable repository reads after capture."""
import json
from ..domain import Scene, Story, VersionRef


class ContextView:
    def __init__(self, repo, db, story_id):
        self.files = repo.files
        self.resolving = set()
        self.freshness_cache = {}
        self.blob_cache = {}
        self.preamble_cache = {}
        self.story = repo._active_story(db, story_id)
        self.scenes = {s.id: s for s in [Scene.model_validate_json(r[0]) for r in db.execute(
            'SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id', (story_id,))]}
        self.versions = {v.id: v for v in [VersionRef.model_validate_json(r[0]) for r in db.execute(
            'SELECT payload FROM versions WHERE story_id=? ORDER BY rowid', (story_id,))]}
        from .impact_validity import load
        self.impact_records,self.impact_applications,self.impact_proofs=load(db,story_id)
        self.impact_current_cache={}
        from ..review.store import load as load_review
        self.review_reports,self.review_acceptances,self.review_operations,self.review_proofs=load_review(db,story_id)
        self.review_current_cache={}
        from .review_authority import load as load_authority
        self.review_authority,self.review_authority_operations=load_authority(db,story_id)
        self.token_profiles = [json.loads(r[0]) for r in db.execute("SELECT payload FROM app_settings WHERE key LIKE 'token_profile:%' ORDER BY key")]
        self.sources = {row[0]:row[1] for row in db.execute('SELECT kind,version_id FROM active_sources WHERE story_id=?',(story_id,))}
        from .import_store import source_files
        self.source_files=source_files(db,story_id)

        from ..dependency_models import AcceptanceRecord
        self.acceptances={}
        self.acceptance_records=[]
        for key,payload in db.execute("SELECT key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid",('acceptance:'+story_id+':%',)):
            record=AcceptanceRecord.model_validate_json(payload)
            if record.story_id!=story_id or key!='acceptance:'+story_id+':'+record.id:
                raise ValueError('Пошкоджений журнал прийняття')
            ref=self.versions.get(record.version_id)
            if not ref or ref.scene_id!=record.scene_id or ref.kind not in {'draft','edited','manual'} or record.baseline.scope!='author_text':
                raise ValueError('Невідповідна версія журналу прийняття')
            self.acceptances[record.version_id]=record
            self.acceptance_records.append(record)

    def list_acceptances(self, story_id):
        """Як Repository.list_acceptances(story_id): усі записи прийняття твору в порядку запису, копіями."""
        self.peek_story(story_id)
        return [r.model_copy(deep=True) for r in self.acceptance_records]

    def token_records(self, kind):
        if kind != 'profile': raise ValueError('Спостереження недоступні в context view')
        import copy
        return copy.deepcopy(self.token_profiles)

    def peek_story(self, id):
        """Внутрішнє читання без копії; не змінювати результат."""
        if id != self.story.id or self.story.trashed_at:
            raise KeyError('Твір недоступний у знімку')
        return self.story

    def peek_scene(self, id):
        """Внутрішнє читання без копії; не змінювати результат."""
        scene = self.scenes[id]
        if scene.trashed_at:
            raise KeyError('Сцена в кошику')
        return scene

    def peek_scenes(self, story_id):
        """Внутрішнє читання без копії; не змінювати результат."""
        self.peek_story(story_id)
        return [s for s in self.scenes.values() if not s.trashed_at]

    def peek_version(self, id):
        """Внутрішнє читання без копії; не змінювати результат. Поле stale не перераховане: див. is_stale."""
        ref = self.versions[id]
        if ref.scene_id:
            self.peek_scene(ref.scene_id)
        return ref

    def is_stale(self, id):
        from . import snapshots
        return snapshots.freshness(self, id).stale

    def get_story(self, id):
        return self.peek_story(id).model_copy(deep=True)

    def get_scene(self, id):
        return self.peek_scene(id).model_copy(deep=True)

    def list_scenes(self, story_id):
        return [s.model_copy(deep=True) for s in self.peek_scenes(story_id)]

    def get_version(self, id):
        result=self.peek_version(id).model_copy(deep=True)
        result.stale=self.is_stale(id)
        return result

    def get_stored_version(self, id):
        """Як Repository.get_version: версія без записів прийняття, рецензії чи пріоритетів лишається зі збереженим stale."""
        ref=self.peek_version(id)
        self.peek_story(ref.story_id)
        legacy=(ref.dependency_snapshot is None and ref.manual_projection_policy is None and ref.id not in self.acceptances
                and not any(r.target.version_id==ref.id for r in self.review_acceptances)
                and not any(scope[0]==ref.scene_id for scope in self.review_authority))
        return ref.model_copy(deep=True) if legacy else self.get_version(id)

    def read_stored_text(self, id):
        ref=self.get_stored_version(id)
        return self.files.read(ref.relative_path,ref.sha256).decode('utf-8')

    def effective_scene(self, id):
        scene=self.get_scene(id)
        prose=self.versions.get(scene.heads.get('prose'))
        if prose and (prose.dependency_snapshot is not None or prose.id in self.acceptances or any(scope[0]==id for scope in self.review_authority) or any(r.target.version_id==prose.id for r in self.impact_records.values()) or any(r.target.version_id==prose.id for r in self.review_acceptances)):
            scene.needs_review=self.is_stale(prose.id)
        elif prose and prose.manual_projection_policy is not None:
            scene.needs_review=scene.needs_review or self.is_stale(prose.id)
        return scene

    def active_source(self, story_id, kind):
        self.get_story(story_id)
        id = self.sources.get(kind)
        return self.get_version(id) if id else None

    def read_text(self, id):
        ref = self.get_version(id)
        return self.read_blob(ref.relative_path, ref.sha256).decode('utf-8')

    def read_blob(self, path, sha):
        key=(path,sha)
        if key not in self.blob_cache:
            self.blob_cache[key]=self.files.read(path,sha)
        return self.blob_cache[key]
