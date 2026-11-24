import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


def test_run_progress_rules():
    """Visible run progress: the progress text, its counts and the book-validation title."""
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/run_progress.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_run_progress_texts_exist_in_both_languages():
    catalogs = json.loads((ROOT / 'src/storygen/web/static/i18n.json').read_text(encoding='utf-8'))
    keys = ['run_progress.book_scene', 'run_progress.book_scene_open', 'run_progress.scene_audit', 'run_progress.generation',
            'run_progress.stage_only', 'run_progress.link_brief', 'run_progress.link_prose', 'run_progress.link_memory',
            'run_progress.stage_brief', 'run_progress.stage_draft', 'run_progress.stage_edit', 'run_progress.stage_memory',
            'run_progress.stage_evaluate', 'run_progress.calls', 'run_progress.calls_open', 'run_progress.spent_bound',
            'run_progress.spent', 'book_validation.menu_running', 'book_validation.menu_stopped', 'book_validation.cancel']
    for locale in ('uk', 'en'):
        missing = [key for key in keys if not catalogs[locale].get(key)]
        assert missing == [], (locale, missing)
    for key in keys:
        uk, en = (sorted(re.findall(r'{(p\d+)}', catalogs[locale][key])) for locale in ('uk', 'en'))
        assert en == uk, key


def test_runs_render_progress_and_reveal_only_runs_started_here():
    runs = (STATIC / 'runs.js').read_text(encoding='utf-8')
    assert "from './run-progress.js'" in runs and "event.type==='progress'" in runs
    assert "'run-reveal'" in runs and 'prefers-reduced-motion' in runs
    page_load = runs.rsplit("api(`/api/stories/${state.storyId}/runs`).then(", 1)[1].split('\n', 1)[0]
    assert 'reveal' not in page_load  # the page load follows without reveal
    css = (STATIC / 'app.css').read_text(encoding='utf-8')
    assert '.run-progress' in css and '.link-button' in css
