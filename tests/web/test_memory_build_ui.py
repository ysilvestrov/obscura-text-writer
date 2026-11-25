"""R-48 memory build (spec §5, §5.1): the story-menu item, the preview dialog and the manuscript-import origin label, read from
the rendered workspace and the static files; the behaviour itself is in tests/web/browser/memory-build.spec.mjs."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.web.app import create_app

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT/'src/storygen/web/static'


def workspace(tmp_path) -> str:
    app = create_app(AppSettings(data_dir=tmp_path))
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        return client.get(f'/stories/{story.id}').text


def test_menu_item_and_dialog_markup(tmp_path):
    html = workspace(tmp_path)
    menu = re.search(r'<nav id="story-menu".*?</nav>', html, re.S).group(0)
    item = re.search(r'<button[^>]*\bid="story-menu-build-memory"[^>]*>', menu)
    assert item and 'hidden' in item.group(0)  # shown only while some scene has no valid memory
    assert 'aria-haspopup="dialog"' in item.group(0) and 'aria-controls="memory-build-dialog"' in item.group(0)
    start = html.index('<dialog id="memory-build-dialog"')
    dialog = html[start:html.index('</dialog>', start)]
    assert 'aria-labelledby="memory-build-title"' in dialog[:300]
    for id in ('memory-build-summary', 'memory-build-cost', 'memory-build-unfit', 'memory-build-cast', 'memory-build-series',
               'memory-build-refresh', 'memory-build-reason', 'memory-build-submit', 'memory-build-cancel'):
        assert f'id="{id}"' in dialog, id
    assert re.search(r'<p id="memory-build-status" role="status"', dialog)
    catalog = json.loads((STATIC/'i18n.json').read_text(encoding='utf-8'))
    for key in set(re.findall(r'data-i18n="([^"]+)"', dialog + item.group(0))):
        assert key in catalog['uk'] and key in catalog['en'], key
    assert 'import {installMemoryBuild} from "/static/memory-build.js"' in html


def test_ui_keys_exist_in_both_languages():
    catalog = json.loads((STATIC/'i18n.json').read_text(encoding='utf-8'))
    script = (STATIC/'memory-build.js').read_text(encoding='utf-8')
    keys = set(re.findall(r"t\('((?:memory_build|manuscript_import)\.[a-z_.]+)'", script))
    assert 'memory_build.ui.cost_unknown' in keys and 'manuscript_import.ui.build_memory' in keys
    for key in keys | {'manuscript_import.ui.origin', 'manuscript_import.ui.plan_optional',
                       'memory_build.server.plan_changed', 'memory_build.server.cast_conflict'}:
        assert key in catalog['uk'] and key in catalog['en'], key
    # The server's refusals are translated by their exact Ukrainian text.
    from storygen.generation.memory_build import MEMORY_PLAN_CHANGED
    from storygen.storage.scene_cast import CAST_CONFLICT
    assert catalog['uk']['memory_build.server.plan_changed'] == MEMORY_PLAN_CHANGED
    assert catalog['uk']['memory_build.server.cast_conflict'] == CAST_CONFLICT


def test_script_follows_the_cost_and_budget_rules():
    script = (STATIC/'memory-build.js').read_text(encoding='utf-8')
    assert 'per_call_usd' not in script  # the total is shown; a per-call price is never multiplied by the calls
    assert 'total_usd' in script and 'memory_plan_fingerprint' in script
    assert "budget_limit_usd:document.querySelector('#run-budget')?.value||null" in script  # as runs.js and book validation
    assert '/scene-cast/infer' in script and 'refreshBook' in script and 'build_memory' in script
    assert 'innerHTML' not in script


def test_origin_label_names_the_manuscript():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT/'tests/web/js/external_origin.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr
    assert 'manuscript_import' in (STATIC/'external-origin.js').read_text(encoding='utf-8')


def test_story_view_names_the_manuscript_of_the_prose_head(tmp_path):
    # R-48 spec §4.4: the scene summary carries the origin of its prose head; an author save replaces it with null.
    from datetime import datetime, timezone
    from storygen.domain import ManuscriptImportOrigin
    from storygen.generation.dependencies import save_manual_prose
    from storygen.storage.manuscript_store import publish_manuscript
    app = create_app(AppSettings(data_dir=tmp_path))
    repo = app.state.repo
    origin = ManuscriptImportOrigin(file_name='mayak.docx', file_sha256='a'*64, imported_at=datetime.now(timezone.utc))
    story, scenes = publish_manuscript(repo, StoryCreate(title='Маяк'), [('Пірс', 'Олена на пірсі.', 'markdown', None, 3),
                                                                        ('Шторм', 'Почався шторм.', 'markdown', None, 2)], origin, False)
    plain = repo.create_scene(story.id, SceneCreate(title='Без прози'))
    save_manual_prose(repo, scenes[1].id, 'Шторм ущух.', repo.get_scene(scenes[1].id).revision)
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        listed = {scene['id']: scene for scene in client.get(f'/api/stories/{story.id}').json()['scenes']}
    assert listed[scenes[0].id]['prose_origin'] == {'kind': 'manuscript_import', 'file_name': 'mayak.docx'}
    assert listed[scenes[1].id]['prose_origin'] is None
    assert listed[plain.id]['prose_origin'] is None
