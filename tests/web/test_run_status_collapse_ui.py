"""R20-WORKSPACE: the run line above the editor is one collapsed line; a failed run opens by itself."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


@pytest.mark.req('R20-WORKSPACE')
def test_run_summary_rules():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/run_summary.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.req('R20-WORKSPACE')
def test_run_status_details_collapse_behind_the_summary():
    runs = (STATIC / 'runs.js').read_text(encoding='utf-8')
    assert "from './run-summary.js'" in runs
    assert "className='run-summary'" in runs and "setAttribute('aria-expanded'" in runs
    assert runs.count('run-detail') >= 5  # plan or its placeholder, messages, stage started, stage finished
    assert "classList.toggle('expanded'" in runs
    assert 'syncRunPrefs(run,runPrefs)' in runs  # a resumed run that fails again opens its error
    css = (STATIC / 'app.css').read_text(encoding='utf-8')
    text_rule = css.split('#run-status .run-summary-text {', 1)[1].split('}', 1)[0]
    assert 'white-space: nowrap' in text_rule and 'text-overflow: ellipsis' in text_rule  # one line even with many models
    assert "className='run-summary-mark'" in runs  # the mark sits outside the truncated text
    assert "className='run-summary-cost'" in runs and 'm_15e66c683330' not in runs  # dollars in the line, raw usage only in the tooltip
    assert '#run-status:not(.expanded) .run-detail' in css and '#run-status:not(.expanded) .memory-violations' in css
    catalog = json.loads((STATIC / 'i18n.json').read_text(encoding='utf-8'))
    assert catalog['uk']['workspace.run_details'] and catalog['en']['workspace.run_details']
