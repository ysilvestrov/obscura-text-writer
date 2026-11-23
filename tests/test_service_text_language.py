"""R26-CLI-LANG-S01 (#32): developer and diagnostic text outside the browser is English only.

The list is explicit: a new service module is added here. Modules shared with the web interface (locking, billing,
evaluation, the gateway) are not listed: the web catalog translates their messages by the Ukrainian original."""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ('billing', 'book', 'character', 'comment', 'memory', 'merge', 'publication', 'series',
          'summary')
SERVICE_MODULES = [
    'src/storygen/server.py', 'src/storygen/maintenance.py', 'src/storygen/evaluation/cli.py',
    'src/storygen/billing/cli.py', 'src/storygen/token_budget/cli.py',
    'src/storygen/desktop.py', 'src/storygen/desktop_tray.py', 'src/storygen/app_window.py', 'src/storygen/win_tray.py',
    'src/storygen/storage/integrity.py', *[f'src/storygen/storage/{name}_checks.py' for name in CHECKS],
    'src/storygen/storage/backup.py', 'src/storygen/storage/pre_migration.py', 'src/storygen/build_edition.py',
    'src/storygen/build_manifest.py', 'src/storygen/self_check.py', 'src/storygen/packaging.py',
    'scripts/build_store.py', 'scripts/tokenizers_notices.py',
]
CYRILLIC = re.compile('[Ѐ-ӿ]')


def cyrillic_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and ast.get_docstring(node, clean=False):
            docstrings.add(id(node.body[0].value))
    name = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name
    return [f'{name}:{node.lineno}: {node.value[:60]!r}' for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
            and CYRILLIC.search(node.value)]


@pytest.mark.req('R26-CLI-LANG')
def test_service_modules_have_no_ukrainian_literals():
    found = [line for module in SERVICE_MODULES for line in cyrillic_literals(ROOT / module)]
    assert found == []


@pytest.mark.req('R26-CLI-LANG')
def test_the_scan_sees_literals_but_not_docstrings(tmp_path):
    sample = tmp_path / 'sample.py'
    lines = ['"""Doc м."""', 'def f():', '    """Doc ф."""', '    return "п"', '']
    sample.write_text('\n'.join(lines), encoding='utf-8')
    assert [line.split(': ', 1)[1] for line in cyrillic_literals(sample)] == [repr('п')]
