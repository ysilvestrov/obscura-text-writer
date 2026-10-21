import shutil,subprocess
from pathlib import Path
import pytest


def test_confirmation_includes_nonblocking_context_warnings():
    node=shutil.which('node')
    if not node:pytest.skip('Node required')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/context_warnings.mjs'),str(root)],capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stderr
