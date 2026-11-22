import sqlite3
import threading
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path


# The schema version a start brings every database to (DESKTOP-001-S03 backs up older ones first).
SCHEMA_VERSION = 7


class _Generation:
    """PERF-001-S06: the data generation of one database file, shared by every Database of that path in the process.
    A commit that wrote adds 1 before it and 1 after it (commit or rollback); in_flight counts such commits."""
    def __init__(self):
        self.lock = threading.Lock()
        self.value = 0
        self.in_flight = 0


_GENERATIONS: dict[Path, _Generation] = {}
_GENERATIONS_LOCK = threading.Lock()


def _generation_of(path: Path) -> _Generation:
    key = path.resolve()
    with _GENERATIONS_LOCK:
        return _GENERATIONS.setdefault(key, _Generation())


class _Connection(sqlite3.Connection):
    """A connection that remembers (generation, commits in flight) at the moment it was opened, before any read."""
    opened: tuple[int, int] = (0, 0)


class Database:
    _before_commit_hook = None  # tests only: runs after a writing commit is marked in flight

    def __init__(self,path: Path):
        self.path=path
        self._generation=_generation_of(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            if db.execute("PRAGMA user_version").fetchone()[0] == 0:
                sql=files("storygen.storage").joinpath("migrations/001_initial.sql").read_text(encoding="utf-8")
                db.executescript("BEGIN IMMEDIATE;\n"+sql+"\nPRAGMA user_version=1;\nCOMMIT;")
            if db.execute("PRAGMA user_version").fetchone()[0] == 1:
                sql=files("storygen.storage").joinpath("migrations/002_trash.sql").read_text(encoding="utf-8")
                db.executescript("BEGIN IMMEDIATE;\n"+sql+"\nPRAGMA user_version=2;\nCOMMIT;")
            if db.execute("PRAGMA user_version").fetchone()[0] == 2:
                sql=files("storygen.storage").joinpath("migrations/003_publication.sql").read_text(encoding="utf-8")
                db.executescript("BEGIN IMMEDIATE;\n"+sql+"\nPRAGMA user_version=3;\nCOMMIT;")
            if db.execute("PRAGMA user_version").fetchone()[0] == 3:
                sql=files("storygen.storage").joinpath("migrations/004_authoring_comments.sql").read_text(encoding="utf-8")
                db.executescript("BEGIN IMMEDIATE;\n"+sql+"\nPRAGMA user_version=4;\nCOMMIT;")
            if db.execute("PRAGMA user_version").fetchone()[0] == 4:
                sql=files("storygen.storage").joinpath("migrations/005_import_sources.sql").read_text(encoding="utf-8")
                db.execute('BEGIN IMMEDIATE')
                # Execute without executescript: payload backfill and schema advance are one transaction.
                for statement in sql.split(';'):
                    if statement.strip():db.execute(statement)
                import json
                from ..scene_description import explicit_scene_number
                for row in db.execute('SELECT id,payload FROM scenes').fetchall():
                    data=json.loads(row['payload'])
                    if 'author_scene_number' not in data:
                        data['author_scene_number']=explicit_scene_number(data.get('beats',''))
                        if data['author_scene_number'] is None:
                            data['author_scene_number']=explicit_scene_number(data.get('title',''))
                        db.execute('UPDATE scenes SET payload=? WHERE id=?',(json.dumps(data,ensure_ascii=False),row['id']))
                db.execute('PRAGMA user_version=5')
            if db.execute("PRAGMA user_version").fetchone()[0] == 5:
                sql=files("storygen.storage").joinpath("migrations/006_series.sql").read_text(encoding="utf-8")
                db.executescript("BEGIN IMMEDIATE;\n"+sql+"\nPRAGMA user_version=6;\nCOMMIT;")
            if db.execute("PRAGMA user_version").fetchone()[0] == 6:
                sql=files("storygen.storage").joinpath("migrations/007_locations.sql").read_text(encoding="utf-8")
                db.execute('BEGIN IMMEDIATE')
                # MEMORY-LOCATIONS: tables, cards and Scene.location_ids of every scene in one transaction.
                for statement in sql.split(';'):
                    if statement.strip():db.execute(statement)
                from .locations import backfill
                backfill(db)
                db.execute('PRAGMA user_version=7')
            if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise ValueError("Непідтримувана версія бази даних")

    def generation(self) -> int:
        with self._generation.lock:
            return self._generation.value

    def opened_state(self, db) -> tuple[int, int]:
        """(generation, writing commits in flight) when this connection was opened, before its first read."""
        return db.opened

    def bump_generation(self) -> None:
        """For tests and tools that wrote to the file without connection(): later reads build a new snapshot."""
        with self._generation.lock:
            self._generation.value += 2

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=5,factory=_Connection)
        state=self._generation
        with state.lock:
            db.opened=(state.value,state.in_flight)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        wrote=False
        try:
            with db:
                try:
                    yield db
                finally:
                    # The only commit point (PERF-001-S06): mark a writing commit before it becomes visible.
                    if db.total_changes:
                        wrote=True
                        with state.lock:
                            state.in_flight+=1
                            state.value+=1
                        if self._before_commit_hook:
                            self._before_commit_hook()
        finally:
            if wrote:
                with state.lock:
                    state.in_flight-=1
                    state.value+=1
            db.close()
