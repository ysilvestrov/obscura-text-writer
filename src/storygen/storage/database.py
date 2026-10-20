import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path


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
            if db.execute("PRAGMA user_version").fetchone()[0] != 2:
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
