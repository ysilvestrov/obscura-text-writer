import shutil
import subprocess
from pathlib import Path

import pytest


def test_horizon_controls_count_and_editor_mode():
    node=shutil.which('node')
    if not node:pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/horizon_controls.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
