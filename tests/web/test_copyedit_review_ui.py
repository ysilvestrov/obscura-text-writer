import shutil
import subprocess
from pathlib import Path

import pytest


def test_copyedit_panel_selection_and_dirty_guards():
    node=shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/copyedit_review.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr


def test_change_review_marks_editor_import():
    import json
    root=Path(__file__).resolve().parents[2]/'src/storygen/web/static'
    script=(root/'change-review.js').read_text(encoding='utf-8')
    catalog=json.loads((root/'i18n.json').read_text(encoding='utf-8'))
    assert "source==='editor_import'" in script
    for key in ('editor_import.proposal_label','editor_import.proposal_note'):
        assert key in script
        for locale in ('uk','en'):
            assert catalog[locale][key].strip(),(locale,key)
