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
