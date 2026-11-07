"""Read-only access to stored stage attempts and version payloads for the offline memory replay."""
from pathlib import Path

from .integrity import readonly_database


class ReadonlyAttempts:
    """Opens the database with mode=ro (immutable when no WAL is pending); never writes."""

    def __init__(self, db: Path):
        self._db = readonly_database(Path(db))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        self._db.close()

    def finished_attempt_payloads(self) -> list[str]:
        rows = self._db.execute("SELECT payload FROM stage_attempts WHERE state IN ('completed','failed')").fetchall()
        return [text for (text,) in rows]

    def version_payload(self, version_id: str) -> str | None:
        row = self._db.execute('SELECT payload FROM versions WHERE id=?', (version_id,)).fetchone()
        return None if row is None else row[0]
