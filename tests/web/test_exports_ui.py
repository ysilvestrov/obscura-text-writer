import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.req('EXPORT-001')
def test_export_form_explicit_options_dirty_and_failure():
    node=shutil.which('node')
    if not node:pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/exports.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr


@pytest.mark.req('EXPORT-001')
def test_export_dialog_fb2_note_starts_hidden_and_local_note_stays():
    template=(Path(__file__).resolve().parents[2]/'src/storygen/web/templates/story.html').read_text(encoding='utf-8')
    dialog=template[template.index('<dialog id="export-dialog"'):template.index('</dialog>',template.index('<dialog id="export-dialog"'))]
    assert '<p id="export-fb2-note" class="muted" hidden>' in dialog
    note=dialog[dialog.index('id="export-fb2-note"'):]
    assert note.index('/publication"')<note.index('</p>')  # the publication-card link belongs to the FB2 note
    assert '<p class="muted"><span data-i18n="export.local_files">' in dialog
