import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.req('UI-FEEDBACK')
def test_scene_status_vocabulary():
    node=shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/workspace_status.mjs'),str(root)],
                          capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
