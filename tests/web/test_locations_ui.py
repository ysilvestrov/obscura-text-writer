"""MEMORY-LOCATIONS-S07: panel rows (node), page wiring, both languages and translated server messages."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.web.app import create_app

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


@pytest.mark.req('MEMORY-LOCATIONS')
def test_panel_rows():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/locations.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.req('MEMORY-LOCATIONS')
def test_locations_page_and_header_button(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Пристань'}).json()
        page = client.get(f'/stories/{story["id"]}/locations').text
        assert 'id="locations-page"' in page and f'data-story-id="{story["id"]}"' in page
        assert 'id="locations-return"' in page and 'id="story-locations"' in page
        assert '/static/locations-panel.js' in page and '/static/editor.js' not in page
        workspace = client.get(f'/stories/{story["id"]}').text
        assert 'id="workspace-locations"' in workspace and f'/stories/{story["id"]}/locations' in workspace
        assert workspace.index('id="workspace-characters"') < workspace.index('id="workspace-locations"') < workspace.index('id="workspace-settings"')
        assert '/static/locations-panel.js' not in workspace
        assert 'data-section="locations"' not in workspace  # WORKSPACE-TOOLS: the side panel holds only scene sections
        assert client.get('/stories/missing/locations').status_code == 404


@pytest.mark.req('MEMORY-LOCATIONS')
def test_both_languages_have_the_texts():
    catalog = json.loads((STATIC / 'i18n.json').read_text(encoding='utf-8'))
    keys = {k for k in catalog['uk'] if k.startswith('locations.')} | {'memory.locations'}
    assert {'locations.nav', 'locations.memory_link', 'locations.page_empty'} <= keys
    assert keys <= set(catalog['en']) and len(keys) > 20


@pytest.mark.req('MEMORY-LOCATIONS')
def test_panel_lives_on_its_page():
    panel = (STATIC / 'locations-panel.js').read_text(encoding='utf-8')
    for gone in ("'./editor.js'", '#memory-view', 'scene-selected', 'story-refreshed', 'refresh('):
        assert gone not in panel, gone
    for here in ('#locations-page', 'dataset.storyId', 'beforeunload', 'returnLink', "'pageshow'", 'liveDrafts('):
        assert here in panel, here
    page = (ROOT / 'src/storygen/web/templates/story.html').read_text(encoding='utf-8')
    assert '/static/locations-link.js' in page


@pytest.mark.req('MEMORY-LOCATIONS')
def test_server_messages_match_the_catalog():
    from storygen.web.localization import translate
    source = (ROOT / 'src/storygen/storage/locations.py').read_text(encoding='utf-8')
    for key in ('locations.error.unknown', 'locations.error.self', 'locations.error.conflict', 'locations.error.unknown_scene',
                'locations.error.plan_place', 'locations.error.not_in_scene'):
        assert translate(key, 'uk') in source, key
    assert translate('locations.error.long', 'uk').replace('{p0}', '{DESCRIPTION_LIMIT}') in source
    # MEMORY-LOCATIONS-S11: glue refusals.
    for key in ('locations.error.glue_slash', 'locations.error.glue_repeat', 'locations.error.glue_no_cut',
                'locations.error.glue_unknown'):
        assert translate(key, 'uk') in source, key
    assert translate('locations.error.glue_length', 'uk').replace('{p0}', '{GLUE_MIN}').replace('{p1}', '{GLUE_MAX}') in source
    assert translate('locations.error.glue_limit', 'uk').replace('{p0}', '{GLUE_LIMIT}') in source
