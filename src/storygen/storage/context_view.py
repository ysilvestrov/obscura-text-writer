"""A captured SQL read view; no mutable repository reads after capture."""
import json
from ..domain import Scene, Story, VersionRef


def memo(source, key, build):
    """PERF-001-S05: the value of build() kept for the life of a ContextView (one request); computed every time for a
    source without a memo (Repository). Only a successful result is kept, so an error is raised again on every call.
    The caller hands out new containers when the value is a list or dict; models in it are shared and read-only."""
    cache = getattr(source, 'memo_cache', None)
    if cache is None:
        return build()
    if key not in cache:
        store = getattr(source, 'immutable', None)
        ref = source.versions.get(key[1]) if store is not None and key[0] in IMMUTABLE_MEMO else None
        if ref is not None:
            # PERF-001-S06: a parse of one version carries over generations, but only after its file passed the
            # stat check of this generation (read_blob raises as before when the file is missing or changed).
            source.read_blob(ref.relative_path, ref.sha256)
            cache[key] = store.parsed((key, ref.sha256), build)
        else:
            cache[key] = build()
    return cache[key]


# Memo kinds whose value depends only on one version's file (key[1] is the version id).
IMMUTABLE_MEMO = frozenset({'memory', 'cards'})


def token_profiles(db):
    """Token profiles are read on every request: storygen-tokens writes them from another process (PERF-001-S06)."""
    return [json.loads(r[0]) for r in db.execute("SELECT payload FROM app_settings WHERE key LIKE 'token_profile:%' ORDER BY key")]


class LayeredCache:
    """PERF-001-S06: the freshness cache of a view over a shared snapshot. Reads look in the request's private layer
    first, then in the shared one; a plain store goes to the shared layer, set_private keeps a result to the request
    (a result computed through a dependency cycle depends on the order of the walk)."""
    def __init__(self, shared):
        self.shared = shared
        self.private = {}

    def __contains__(self, key):
        return key in self.private or key in self.shared

    def __getitem__(self, key):
        return self.private[key] if key in self.private else self.shared[key]

    def get(self, key, default=None):
        return self[key] if key in self else default

    def __setitem__(self, key, value):
        self.shared[key] = value

    def set_private(self, key, value):
        self.private[key] = value


class SharedState:
    """The read-only part of a ContextView one data generation shares between requests (PERF-001-S06)."""
    def __init__(self, fields, fresh):
        import threading
        self.fields = fields
        self.fresh = fresh
        self.lock = threading.RLock()


# Captured models and caches of values that depend only on the snapshot; never the walk state or sentinel caches.
SHARED_FIELDS = ('files', 'story', 'scenes', 'versions', 'sources', 'source_files', 'acceptances', 'acceptance_records', 'link_verdicts',
                 'blob_cache', 'preamble_cache', 'journal_cache', 'memo_cache', 'immutable', 'locations')


class ContextView:
    def __init__(self, repo, db, story_id):
        self.files = repo.files
        self.immutable = getattr(repo, 'immutable', None)
        self.resolving = set()
        self.cycle_hits = 0  # dependency cycles met so far; a result whose walk met one stays private
        self.shared_lock = None
        self.freshness_cache = {}
        self.blob_cache = {}
        self.preamble_cache = {}
        self.journal_cache = {}
        # PERF-001-S05: parsed cards and memory journals by version, and per-scene derived values (protagonists, names,
        # memory projection policy). Lives as long as the view (one request); entries are shared and never modified.
        self.memo_cache = {}
        self.story = repo._active_story(db, story_id)
        self.scenes = {s.id: s for s in [Scene.model_validate_json(r[0]) for r in db.execute(
            'SELECT payload FROM scenes WHERE story_id=? ORDER BY position,id', (story_id,))]}
        self.versions = {v.id: v for v in [VersionRef.model_validate_json(r[0]) for r in db.execute(
            'SELECT payload FROM versions WHERE story_id=? ORDER BY rowid', (story_id,))]}
        self.token_profiles = token_profiles(db)
        self.sources = {row[0]:row[1] for row in db.execute('SELECT kind,version_id FROM active_sources WHERE story_id=?',(story_id,))}
        from .import_store import source_files
        self.source_files=source_files(db,story_id)
        from .locations import load_locations
        self.locations=load_locations(db,story_id)  # MEMORY-LOCATIONS: cards, merges and descriptions of the story

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
        from .link_records import load_verdicts
        self.link_verdicts=load_verdicts(db,story_id,self.scenes)  # VALID-LINKS: author and auditor verdicts

    def shared_state(self):
        """The state to publish for this view's generation; the view itself is unchanged until adopt()."""
        return SharedState({name: getattr(self, name) for name in SHARED_FIELDS}, self.freshness_cache)

    def adopt(self, state):
        """Turn this freshly captured view into a request view over the published state (its own models)."""
        self.freshness_cache = LayeredCache(state.fresh)
        self.shared_lock = state.lock

    @classmethod
    def from_state(cls, state, db):
        """A request view over a published state: shared models and results, its own walk state and token profiles."""
        view = cls.__new__(cls)
        view.__dict__.update(state.fields)
        view.resolving = set()
        view.cycle_hits = 0
        view.freshness_cache = LayeredCache(state.fresh)
        view.shared_lock = state.lock
        view.token_profiles = token_profiles(db)
        return view

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
        """Перерахована актуальність версії. Не перевіряє кошик і існування сцени/твору: викликач перевіряє сам (peek_version/get_version)."""
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

    def peek_version_stale(self, id):
        """Внутрішнє читання без копії: (версія, перерахована актуальність) у тому самому порядку викликів, що get_version.
        Не змінювати версію й не повертати її викликачам (PERF-001)."""
        ref=self.peek_version(id)
        return ref,self.is_stale(id)

    def get_stored_version(self, id):
        """Як Repository.get_version: версія без знімка й запису прийняття лишається зі збереженим stale."""
        ref=self.peek_version(id)
        self.peek_story(ref.story_id)
        from .snapshots import HEAD_LINK
        legacy=ref.dependency_snapshot is None and ref.manual_projection_policy is None and ref.id not in self.acceptances and ref.kind not in HEAD_LINK
        return ref.model_copy(deep=True) if legacy else self.get_version(id)

    def read_stored_text(self, id):
        ref=self.get_stored_version(id)
        return self.files.read(ref.relative_path,ref.sha256).decode('utf-8')

    def effective_scene(self, id):
        scene=self.get_scene(id)
        # VALID-LINKS: the prose needs review exactly when its head is stale (Z2 does not hold and the author has not
        # accepted it); the stored flag is no longer read.
        prose=self.versions.get(scene.heads.get('prose'))
        scene.needs_review=bool(prose) and self.is_stale(prose.id)
        return scene

    def active_source(self, story_id, kind):
        self.get_story(story_id)
        id = self.sources.get(kind)
        return self.get_version(id) if id else None

    def read_text(self, id):
        # PERF-001: no deep copy; is_stale is still asked, so freshness_cache fills in the same order as before.
        ref, _ = self.peek_version_stale(id)
        return self.read_blob(ref.relative_path, ref.sha256).decode('utf-8')

    def read_blob(self, path, sha):
        key=(path,sha)
        if key not in self.blob_cache:
            store=getattr(self,'immutable',None)
            self.blob_cache[key]=store.read(self.files,path,sha) if store is not None else self.files.read(path,sha)
        return self.blob_cache[key]


def version_and_stale(source, id):
    """(version, stale) for a context view without a deep copy, for a repository through its public read. The version
    must not be changed or handed to a caller (PERF-001)."""
    if isinstance(source, ContextView):
        return source.peek_version_stale(id)
    ref = source.get_version(id)
    return ref, ref.stale
