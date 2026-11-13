"""MEMORY-MERGE-S04: pure helpers of the merge window (node) and the wiring of the story page."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_merge_window_rows_choices_and_payload():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/memory_merge.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


def test_story_page_loads_the_merge_window():
    assert '/static/memory-merge-panel.js' in (ROOT / 'src/storygen/web/templates/story.html').read_text(encoding='utf-8')


def test_merge_refusals_are_translated():
    from storygen.memory.previous import MERGE_REQUIRED
    from storygen.storage.memory_merges import CHANGED
    from storygen.web.localization import translate
    assert translate('merge.server.required', 'uk') == MERGE_REQUIRED
    assert translate('merge.server.changed', 'uk') == CHANGED
    assert translate('merge.server.required', 'en').startswith('Confirm the memory merge')


def test_stop_link_matches_the_server_message():
    from storygen.memory.previous import MERGE_REQUIRED
    assert f"const REQUIRED='{MERGE_REQUIRED}'" in (ROOT / 'src/storygen/web/static/memory-merge-panel.js').read_text(encoding='utf-8')
