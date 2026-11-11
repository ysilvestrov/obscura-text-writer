"""MCP-BRIDGE: the workspace shows which external chat client wrote a version."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


@pytest.mark.req('MCP-BRIDGE')
def test_external_origin_label():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/external_origin.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.req('MCP-BRIDGE')
def test_history_and_status_row_show_the_label():
    template = (ROOT / 'src/storygen/web/templates/story.html').read_text(encoding='utf-8')
    row = re.search(r'<section id="workspace-status-row".*?</section>', template, re.S).group(0)
    assert re.search(r'<p id="workspace-origin"[^>]*\bhidden\b', row)
    editor = (STATIC / 'editor.js').read_text(encoding='utf-8')
    versions = (STATIC / 'versions.js').read_text(encoding='utf-8')
    assert "from './external-origin.js'" in editor and "from './external-origin.js'" in versions
    # Rendering itself is exercised in external_origin.mjs; here only that the editor routes every buffer change to it.
    assert "function renderOrigin(ref){renderOriginInto(document.querySelector('#workspace-origin'),ref)}" in editor
    load = editor[editor.index('export function loadBuffer('):].split('\n}', 1)[0]
    assert 'renderOrigin(ref)' in load
    # An author save replaces the version in the buffer: the label follows the saved version, not the one loaded.
    assert re.search(r"textEditor\.markSaved\(\{[^;]*source_ref:result\.version\}\);\s*renderOrigin\(result\.version\)", editor)
    assert re.search(r"externalOriginLabel\(ref\)", versions)
    assert 'innerHTML' not in (STATIC / 'external-origin.js').read_text(encoding='utf-8')


@pytest.mark.req('MCP-BRIDGE')
def test_trashing_the_last_scene_clears_the_label():
    editor = (STATIC / 'editor.js').read_text(encoding='utf-8')
    # #105: the trash callback is the shared clearSceneBuffer, also used when the scene goes to the trash elsewhere.
    assert 'installSceneTrash(state,refresh,clearSceneBuffer)' in editor
    callback = editor[editor.index('export function clearSceneBuffer'):].split('\n', 1)[0]
    assert 'renderOrigin(null)' in callback


@pytest.mark.req('MCP-BRIDGE')
@pytest.mark.parametrize('language', ['uk', 'en'])
def test_instructions_register_claude_code_for_every_folder(language):
    page = (ROOT / f'docs/site/{language}/mcp.md').read_text(encoding='utf-8')
    assert 'claude mcp add --scope user obscura -- ' in page
    assert 'claude mcp add obscura' not in page
    assert 'Сцену вже змінено' in page and 'Контекст сцени змінився' in page
    assert 'ChatGPT desktop' not in page
