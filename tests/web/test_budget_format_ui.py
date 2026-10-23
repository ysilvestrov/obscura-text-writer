import shutil
import subprocess
from pathlib import Path

import pytest


def test_last_call_amount_and_cost_status_labels():
    node=shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/budget_format.mjs'),str(root)],
                          capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
