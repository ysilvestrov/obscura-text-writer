"""MEMORY-LOCATIONS-S07: panel rows (node), page wiring, both languages and translated server messages."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


@pytest.mark.req('MEMORY-LOCATIONS')
def test_panel_rows_and_shared_revision():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/locations.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.req('MEMORY-LOCATIONS')
def test_story_page_has_the_section_and_both_languages_have_the_texts():
    page = (ROOT / 'src/storygen/web/templates/story.html').read_text(encoding='utf-8')
    assert '/static/locations-panel.js' in page
    assert 'data-section="locations"' not in page  # WORKSPACE-TOOLS: the side panel holds only scene sections
    catalog = json.loads((STATIC / 'i18n.json').read_text(encoding='utf-8'))
    keys = {k for k in catalog['uk'] if k.startswith('locations.')} | {'memory.locations'}
    assert keys <= set(catalog['en']) and len(keys) > 20


@pytest.mark.req('MEMORY-LOCATIONS')
def test_server_messages_match_the_catalog():
    from storygen.web.localization import translate
    source = (ROOT / 'src/storygen/storage/locations.py').read_text(encoding='utf-8')
    for key in ('locations.error.unknown', 'locations.error.self', 'locations.error.conflict'):
        assert translate(key, 'uk') in source, key
    assert translate('locations.error.long', 'uk').replace('{p0}', '{DESCRIPTION_LIMIT}') in source
