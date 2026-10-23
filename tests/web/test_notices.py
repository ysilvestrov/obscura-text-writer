import shutil,subprocess
from pathlib import Path
import pytest


def test_notices_close_and_scene_selection():
    node=shutil.which('node')
    if not node:pytest.skip('Node required')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/notices.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
