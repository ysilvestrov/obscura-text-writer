"""PERF-001-S06: one captured story snapshot shared by the reads of a data generation (#39, part 2).

A read outside a write transaction gets a request view over the published state of (story, generation) when its
connection saw no writing commit in flight when it was opened and no writing commit happened since. Otherwise it
captures a private view; that view is published when, after the capture, the generation is still the one seen at
open. Only the newest generation of a few stories is kept; an older one never replaces a newer one."""
import threading
from collections import OrderedDict


class SnapshotStore:
    def __init__(self, limit=4):
        self.limit = limit
        self.lock = threading.Lock()
        self.items = OrderedDict()

    def get(self, story_id, generation):
        with self.lock:
            item = self.items.get(story_id)
            if item is None or item[0] != generation:
                return None
            self.items.move_to_end(story_id)
            return item[1]

    def publish(self, story_id, generation, state):
        """The stored state for this generation, or None when a newer generation is already kept."""
        with self.lock:
            item = self.items.get(story_id)
            if item is not None and item[0] > generation:
                return None
            if item is not None and item[0] == generation:
                return item[1]
            self.items[story_id] = (generation, state)
            self.items.move_to_end(story_id)
            while len(self.items) > self.limit:
                self.items.popitem(last=False)
            return state


def _unchanged(database, db, generation, in_flight):
    return in_flight == 0 and not db.total_changes and database.generation() == generation


def read_view(repo, db, story_id):
    """A ContextView for a read on `db` (opened by repo.db.connection(), no writes on it)."""
    from .context_view import ContextView
    store = repo.snapshots
    generation, in_flight = repo.db.opened_state(db)
    if _unchanged(repo.db, db, generation, in_flight):
        state = store.get(story_id, generation)
        if state is not None:
            return ContextView.from_state(state, db)
    view = ContextView(repo, db, story_id)
    # Checked after the whole capture: no writing commit started since the connection was opened, so the rows read
    # are the state of `generation`.
    if _unchanged(repo.db, db, generation, in_flight):
        state = view.shared_state()
        published = store.publish(story_id, generation, state)
        if published is state:
            view.adopt(state)
        elif published is not None:
            # A parallel capture of the same generation published first: share its state, so the top level of
            # freshness is still computed once.
            return ContextView.from_state(published, db)
    return view


class ImmutableStore:
    """PERF-001-S06: what carries over from one generation to the next. File contents by (path, sha256), reused only
    while os.stat gives the same size and mtime (otherwise read and verified again by FileStore.read), and parses
    that depend only on such a file (memory journals, character cards). Bounded, least recently used out."""
    def __init__(self, max_bytes=128 * 1024 * 1024, max_parsed=8192):
        self.max_bytes = max_bytes
        self.max_parsed = max_parsed
        self.lock = threading.Lock()
        self.blobs = OrderedDict()  # (path, sha) -> (stat key, bytes)
        self.size = 0
        self.parses = OrderedDict()  # (memo key, sha) -> value

    def read(self, files, path, sha):
        try:
            info = files.resolve(path).stat()
            stat = (info.st_size, info.st_mtime_ns)
        except OSError:
            return files.read(path, sha)  # raises the usual corruption error
        key = (path, sha)
        with self.lock:
            entry = self.blobs.get(key)
            if entry is not None and entry[0] == stat:
                self.blobs.move_to_end(key)
                return entry[1]
        data = files.read(path, sha)
        with self.lock:
            old = self.blobs.pop(key, None)
            if old is not None:
                self.size -= len(old[1])
            self.blobs[key] = (stat, data)
            self.size += len(data)
            while self.size > self.max_bytes and self.blobs:
                _, (_, dropped) = self.blobs.popitem(last=False)
                self.size -= len(dropped)
        return data

    def parsed(self, key, build):
        with self.lock:
            if key in self.parses:
                self.parses.move_to_end(key)
                return self.parses[key]
        value = build()
        with self.lock:
            self.parses[key] = value
            while len(self.parses) > self.max_parsed:
                self.parses.popitem(last=False)
        return value
