import shutil
import subprocess
from pathlib import Path

import pytest


def test_loop_limit_and_confirmation_only_name_editor():
    node=shutil.which('node')
    if not node:pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/run_readiness.mjs')],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
