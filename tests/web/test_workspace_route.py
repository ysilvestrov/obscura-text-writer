import shutil
import subprocess
from pathlib import Path
import pytest


def test_workspace_route_save_and_source_regressions():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required for browser module tests')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, str(root/'tests/web/js/workspace_route.mjs')],
                            capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr


def test_workspace_controller_guards_async_save_and_review():
    node=shutil.which('node')
    if not node:pytest.skip('Node required')
    result=subprocess.run([node,str(Path(__file__).parent/'js/workspace_controller.mjs')],capture_output=True,encoding='utf8',timeout=20)
    assert result.returncode==0,result.stderr
