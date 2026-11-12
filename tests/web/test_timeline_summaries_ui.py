"""MEMORY-SUMMARY-S07: panel rows (node), page wiring, translated server messages and request statistics."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


def test_panel_rows():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/timeline_summaries.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


def test_story_page_loads_the_panel_and_both_languages_have_the_texts():
    assert '/static/timeline-summaries-panel.js' in (ROOT / 'src/storygen/web/templates/story.html').read_text(encoding='utf-8')
    catalog = json.loads((STATIC / 'i18n.json').read_text(encoding='utf-8'))
    keys = {k for k in catalog['uk'] if k.startswith('summaries.')} | {'memory.layer.summary', 'stats.memory_summaries'}
    assert keys <= set(catalog['en']) and len(keys) > 20


def test_server_messages_match_the_catalog():
    from storygen.memory.selection import SUMMARY_STALE_WARNING
    from storygen.web.localization import translate
    assert translate('summaries.warning.stale', 'uk').replace('{p0}', '1').replace('{p1}', '10') == SUMMARY_STALE_WARNING.format(first=1, last=10)
    source = (ROOT / 'src/storygen/generation/timeline_summary.py').read_text(encoding='utf-8') + \
        (ROOT / 'src/storygen/storage/timeline_summaries.py').read_text(encoding='utf-8') + \
        (ROOT / 'src/storygen/generation/worker.py').read_text(encoding='utf-8')
    for key in ('summaries.error.unpublished', 'summaries.error.conflict', 'summaries.error.no_block', 'summaries.error.no_role',
                'summaries.error.running', 'summaries.error.empty', 'summaries.error.publish_conflict', 'summaries.error.block_memory'):
        assert translate(key, 'uk') in source, key


def test_statistics_count_summaries_in_the_request():
    from storygen.application.statistics import memory_summary
    metrics = {'selection': {'layers': {'core': 1, 'summary': 1, 'timeline': 4}, 'dropped': {'timeline': 2},
                             'summaries': [{'block_key': 'range:1-10', 'version_id': 'v'}]}}
    summary = memory_summary(metrics)['memory_selection']
    assert summary['summaries'] == 1 and summary['layers']['summary'] == 1
    assert memory_summary({'selection': {'layers': {'core': 1}, 'dropped': {}}})['memory_selection']['summaries'] == 0
