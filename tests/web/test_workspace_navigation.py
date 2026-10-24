import shutil
import subprocess
from pathlib import Path
import pytest


def test_workspace_settings_links_and_usage_are_explicit():
    node=shutil.which('node')
    if not node:pytest.skip('Node required')
    result=subprocess.run([node,str(Path(__file__).parent/'js/workspace_navigation.mjs')],capture_output=True,encoding='utf8',timeout=15)
    assert result.returncode==0,result.stderr
