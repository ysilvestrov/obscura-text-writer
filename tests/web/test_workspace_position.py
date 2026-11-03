import shutil,subprocess
from pathlib import Path
import pytest


def test_workspace_position_preferences_and_fallbacks():
    node=shutil.which('node')
    if not node:
        bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        if not bundled.is_file():pytest.skip('Node required for frontend helper test')
        node=str(bundled)
    result=subprocess.run([node,str(Path(__file__).parents[2]/'tests/web/js/workspace-position.mjs')],capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
