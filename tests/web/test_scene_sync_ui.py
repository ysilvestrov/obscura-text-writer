"""MCP-BRIDGE (#105): the open workspace picks up scene changes made elsewhere without losing unsaved text."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


@pytest.mark.req('MCP-BRIDGE')
def test_scene_sync_rules():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/scene_sync.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


def _read(name):
    return (STATIC / name).read_text(encoding='utf-8')


@pytest.mark.req('MCP-BRIDGE')
def test_open_rewrite_from_memory_blocks_buffer_replacement():
    versions = _read('versions.js')
    handler = versions[versions.index("addEventListener('story-refreshed'"):]
    handler = handler[:handler.index('await render()')]
    assert handler.count('ghostOpen()') == 2


@pytest.mark.req('MCP-BRIDGE')
def test_material_and_tab_status_come_from_the_fresh_view():
    versions = _read('versions.js')
    assert 'newerScene(state.view.scenes.find(s=>s.id===state.scene.id),state.scene)' in versions
    assert 'liveScene(state.scene,state.view?.scenes).heads[kind]' in versions
    route = _read('workspace-route.js')
    tabs = route[route.index("for(const b of document.querySelectorAll('#mode-tabs button'))"):]
    assert 'live?.heads?.[head]' in tabs and 'state.scene?.heads[head]' not in tabs


@pytest.mark.req('MCP-BRIDGE')
def test_buffer_flags_and_save_refusal_for_a_scene_trashed_elsewhere():
    editor = _read('editor.js')
    load = editor[editor.index('export function loadBuffer'):editor.index('export async function saveBuffer')]
    assert 'state.externalChange=false' in load
    save = editor[editor.index('export async function saveBuffer'):editor.index('export async function refresh')]
    assert "externalNotice(state)==='gone'" in save
    refresh = editor[editor.index('export async function refresh'):editor.index('export async function selectScene')]
    assert 'state.refreshing=(state.refreshing||0)+1' in refresh and 'finally' in refresh
    assert 'export function clearSceneBuffer' in editor and 'installSceneTrash(state,refresh,clearSceneBuffer)' in editor


@pytest.mark.req('MCP-BRIDGE')
def test_workspace_loads_the_sync_and_its_notice():
    template = (ROOT / 'src/storygen/web/templates/story.html').read_text(encoding='utf-8')
    assert 'id="external-change"' in template and '/static/scene-sync-workspace.js' in template
    wiring = _read('scene-sync-workspace.js')
    for needle in ("'visibilitychange'", "'focus'", '/scene-revisions', "invokeWorkspaceCommand('show',state.mode)", 'clearSceneBuffer()'):
        assert needle in wiring
    import json
    catalog = json.loads(_read('i18n.json'))
    for key in ('sync.changed', 'sync.open_newer', 'sync.trashed'):
        assert catalog['uk'][key] and catalog['en'][key]
    assert catalog['uk']['sync.changed'] == 'Сцену змінено ззовні'
    assert catalog['en']['sync.open_newer'] == 'Open the newer version'
