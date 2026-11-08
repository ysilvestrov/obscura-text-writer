import shutil
import subprocess
from pathlib import Path

import pytest


def test_identical_concurrent_gets_share_one_fetch():
    node=shutil.which('node')
    if not node:pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/api_coalesce.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=30)
    assert result.returncode==0,result.stderr+result.stdout
