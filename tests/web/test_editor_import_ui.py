"""EDITOR-IMPORT UI: the story-menu item and the import dialog, read from the rendered page and the static files."""
import json
import re
from pathlib import Path

import pytest

from tests.web.test_workspace_layout_ui import page

STATIC = Path(__file__).resolve().parents[2]/'src/storygen/web/static'


@pytest.mark.req('EDITOR-IMPORT')
def test_editor_import_dialog_markup(tmp_path):
    tree, html = page(tmp_path)
    menu = html[html.index('<nav id="story-menu"'):html.index('</nav>', html.index('<nav id="story-menu"'))]
    items = re.findall(r'<li[^>]*>\s*<(?:button|a)[^>]*\bid="([^"]+)"', menu)
    assert items[items.index('export-story')+1] == 'import-edition'
    item = tree.attrs['import-edition']
    assert '#story-menu' in tree.ancestors['import-edition']
    assert item.get('aria-haspopup') == 'dialog' and item.get('aria-controls') == 'editor-import-dialog'
    start = html.index('<dialog id="editor-import-dialog"')
    dialog = html[start:html.index('</dialog>', start)]
    assert re.search(r'class="export-dialog[ "]', dialog[:200]) and 'aria-labelledby="editor-import-title"' in dialog[:200]
    assert re.search(r'<input[^>]*type="file"[^>]*accept="[^"]*\.docx', dialog)
    assert re.search(r'<p id="editor-import-status" role="status"', dialog)
    for id in ('editor-import-file', 'editor-import-status', 'editor-import-submit', 'editor-import-cancel',
               'editor-import-abort', 'editor-import-skip', 'editor-import-replace'):
        assert '#editor-import-dialog' in tree.ancestors[id], id
    catalog = json.loads((STATIC/'i18n.json').read_text(encoding='utf-8'))
    keys = set(re.findall(r'data-i18n="([^"]+)"', dialog+menu[menu.index('id="import-edition"'):]))
    assert 'editor_import.menu' in keys and 'editor_import.title' in keys
    for key in keys:
        assert key in catalog['uk'] and key in catalog['en'], key
    assert '<script type="module" src="/static/editor-imports.js"></script>' in html


@pytest.mark.req('EDITOR-IMPORT')
def test_editor_import_strings_and_server_texts():
    catalog = json.loads((STATIC/'i18n.json').read_text(encoding='utf-8'))
    assert catalog['uk']['editor_import.menu'] == 'Імпорт редакції (DOCX)…'
    assert catalog['en']['editor_import.menu'] == "Import editor's revision (DOCX)…"
    for status in ('changed', 'comments_only', 'unchanged', 'changed_since_export', 'over_limit', 'unknown_base',
                   'no_prose', 'unsupported_markup', 'pending_review'):
        key = f'editor_import.status.{status}'
        assert catalog['uk'].get(key) and catalog['en'].get(key), key
    assert catalog['uk']['editor_import.replace_hint'] == 'Ваші пізніші зміни з’являться як правки, які можна відхилити'
    assert [catalog['uk'][f'editor_import.{key}'] for key in ('abort', 'skip', 'replace')] == [
        'Скасувати імпорт', 'Пропустити змінені сцени', 'Замінити все']
    script = (STATIC/'editor-import.js').read_text(encoding='utf-8')
    # Server texts (warnings, errors) arrive in Ukrainian; every one passes through diagnostic().
    assert 'diagnostic(' in script and 'state.dirty' in script and 'state.saving' in script
    assert "method:'DELETE'" in script and '20*1024*1024' in script
    wiring = (STATIC/'editor-imports.js').read_text(encoding='utf-8')
    assert 'installEditorImport(' in wiring


@pytest.mark.req('EDITOR-IMPORT')
def test_editor_import_final_review_fixes():
    catalog = json.loads((STATIC/'i18n.json').read_text(encoding='utf-8'))
    # Plural-free wording: «1 сцен» / «1 scenes» cannot appear.
    assert catalog['uk']['editor_import.import'] == 'Імпортувати сцени: {p0}'
    assert catalog['en']['editor_import.import'] == 'Import scenes: {p0}'
    # The result line names the tab by its real English label.
    assert catalog['en']['m_c2320838b6df'] == 'Editing'
    assert 'Editing tab' in catalog['en']['editor_import.where']
    script = (STATIC/'editor-import.js').read_text(encoding='utf-8')
    # A running save keeps its file: no DELETE while saving, and the list is refreshed even if the dialog was closed.
    assert re.search(r'const discard=\(\)=>\{\s*if\(!pending\|\|saving\)return;', script)
    assert re.search(r'if\(mine!==epoch\)\{try\{await refresh\?\.\(\)\}catch\{\}return\}', script)
    # 409/404: the flags are cleared before the file input is focused, otherwise focus() hits a disabled input.
    assert re.search(r'busy=saving=false;discard\(\);preview=null;[^\n]*show\(\'pick\'\);\s*setStatus[^\n]*input\.focus\(\)', script)
    # Editor warnings in the review panel go through diagnostic() so the English panel shows English.
    review = (STATIC/'change-review.js').read_text(encoding='utf-8')
    assert '.map(diagnostic).join' in review
    assert not re.search(r'warnings(\|\|\[\])?\)?\.join\(', review.replace('.map(diagnostic).join', ''))
