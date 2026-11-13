"""MEMORY-MERGE: the memory a scene extends is named only by memory/previous.py; a direct read of the last ancestor's
memory head would skip the merge of a scene after a merge point."""
import re
from pathlib import Path

PATTERN = re.compile(r"\[-[12]\]\.heads(\.get\(|\[)'memory'|\(previous\[-1\], *'memory'\)|\(prefix\[-2\], *'memory'\)")
ALLOWED = {'memory/previous.py'}


def test_no_previous_memory_reads_outside_previous_py():
    root = Path(__file__).resolve().parents[1] / 'src' / 'storygen'
    found = [f'{path.relative_to(root).as_posix()}:{n}' for path in root.rglob('*.py')
             if path.relative_to(root).as_posix() not in ALLOWED
             for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1) if PATTERN.search(line)]
    assert found == []
