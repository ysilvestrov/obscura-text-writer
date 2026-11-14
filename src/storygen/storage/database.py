import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path


# The schema version a start brings every database to (DESKTOP-001-S03 backs up older ones first).
SCHEMA_VERSION = 6


class Database:
    def __init__(self,path: Path):
        self.path=path
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
            if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise ValueError("Непідтримувана версія бази даних")

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=5)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        try:
            with db:
                yield db
        finally:
            db.close()
