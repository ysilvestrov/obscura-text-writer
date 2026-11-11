"""DESKTOP-001: where the installed build keeps the copies it makes before a schema migration."""
from pathlib import Path


def backups_dir(data_dir: Path) -> Path:
    # Next to the data folder, never inside it: the verified backup refuses a nested destination (MAINT-002).
    data_dir = Path(data_dir)
    return data_dir.parent / (data_dir.name + '-backups')
