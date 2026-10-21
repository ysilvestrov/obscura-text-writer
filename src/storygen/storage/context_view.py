"""A captured SQL read view; no mutable repository reads after capture."""
import json
from ..domain import Scene, Story, VersionRef


class ContextView:
    def __init__(self, repo, db, story_id):
        self.files = repo.files
        self.resolving = set()
        self.freshness_cache = {}
        self.blob_cache = {}
        self.story = repo._active_story(db, story_id)
        self.scenes = {s.id: s for s in [Scene.model_validate_json(r[0]) for r in db.execute(
            'SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id', (story_id,))]}
        self.versions = {v.id: v for v in [VersionRef.model_validate_json(r[0]) for r in db.execute(
            'SELECT payload FROM versions WHERE story_id=? ORDER BY rowid', (story_id,))]}
        self.sources = {}
        for row in db.execute('SELECT payload FROM source_files WHERE story_id=? ORDER BY rowid', (story_id,)):
            source = json.loads(row[0])
            self.sources[source['kind']] = source['version_id']

        from ..dependency_models import AcceptanceRecord
        self.acceptances={}
        for key,payload in db.execute("SELECT key,payload FROM app_settings WHERE key LIKE ? ORDER BY rowid",('acceptance:'+story_id+':%',)):
            record=AcceptanceRecord.model_validate_json(payload)
            if record.story_id!=story_id or key!='acceptance:'+story_id+':'+record.id:
                raise ValueError('Пошкоджений журнал прийняття')
            ref=self.versions.get(record.version_id)
            if not ref or ref.scene_id!=record.scene_id or ref.kind not in {'draft','edited','manual'} or record.baseline.scope!='author_text':
                raise ValueError('Невідповідна версія журналу прийняття')
            self.acceptances[record.version_id]=record

    def get_story(self, id):
        if id != self.story.id or self.story.trashed_at:
            raise KeyError('Твір недоступний у знімку')
        return self.story.model_copy(deep=True)

    def get_scene(self, id):
        scene = self.scenes[id]
        if scene.trashed_at:
            raise KeyError('Сцена в кошику')
        return scene.model_copy(deep=True)

    def list_scenes(self, story_id):
        self.get_story(story_id)
        return [s.model_copy(deep=True) for s in self.scenes.values() if not s.trashed_at]

    def get_version(self, id):
        ref = self.versions[id]
        if ref.scene_id:
            self.get_scene(ref.scene_id)
        from .snapshots import resolve_freshness
        result=ref.model_copy(deep=True)
        result.stale=resolve_freshness(self,id).stale
        return result

    def effective_scene(self, id):
        scene=self.get_scene(id)
        prose=self.versions.get(scene.heads.get('prose'))
        if prose and (prose.dependency_snapshot is not None or prose.id in self.acceptances):
            scene.needs_review=self.get_version(prose.id).stale
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
