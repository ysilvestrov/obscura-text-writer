import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.req('WORKSPACE-TOOLS')
def test_scene_sections_remember_their_state_without_requiring_storage():
    node=shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/tool_sections.mjs'),str(root)],
                          capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
