"""BOOK-LINEAGE-S04: tracked characters come from the scene's arcs; the book-wide helper is read only through book/protagonists."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / 'src/storygen'
CALL = re.compile(r'\btracked_characters\(')
# memory/core.py defines the book-wide inference; snapshots.py evaluates the legacy story selector with it.
ALLOWED = {'memory/core.py', 'book/protagonists.py', 'storage/snapshots.py'}


def test_tracked_characters_is_called_only_by_the_protagonist_module():
    found = sorted(f'{path.relative_to(SRC).as_posix()}:{n}' for path in SRC.rglob('*.py')
                   for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
                   if CALL.search(line) and path.relative_to(SRC).as_posix() not in ALLOWED)
    assert found == []
