"""BOOK-STRUCTURE-S06: pure helpers of the structure interface (node) and the wiring of the pages."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


def test_group_rows_arc_options_and_panel_buffer():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/book_structure.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


def test_pages_load_the_structure_modules():
    assert '/static/book-structure-ui.js' in (ROOT / 'src/storygen/web/templates/story.html').read_text(encoding='utf-8')
    assert '/static/book-structure-panel.js' in (ROOT / 'src/storygen/web/templates/settings.html').read_text(encoding='utf-8')
    assert "groupScenes(" in (STATIC / 'editor.js').read_text(encoding='utf-8')


def test_server_refusals_are_translated():
    from storygen.book.guard import NO_LONG_PROSE, READ_ONLY
    from storygen.web.localization import translate
    assert translate('book.readonly', 'uk') == READ_ONLY
    assert translate('book.no_long_prose', 'uk') == NO_LONG_PROSE
    assert translate('book.readonly', 'en').startswith('This book has parts or arcs')


def test_book_modules_ask_the_book_not_the_build():
    """LONG-PROSE-TRIAL-S07: a trial book is a book with long prose; no book module reads the build's long_prose."""
    for name in ('book-structure-ui.js', 'book-structure-panel.js', 'memory-build.js', 'series-facts.js'):
        text = (STATIC / name).read_text(encoding='utf-8')
        assert 'info.long_prose' not in text, name
        assert 'long_prose' in text, name
    for name in ('book-structure-ui.js', 'book-structure-panel.js'):
        assert "from './long-prose-trial.js'" in (STATIC / name).read_text(encoding='utf-8'), name
