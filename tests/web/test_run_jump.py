import shutil,subprocess
from pathlib import Path
import pytest


@pytest.mark.req('R20-WORKSPACE')
def test_run_jump_link_follows_waiting_runs_and_review_card():
    node=shutil.which('node')
    if not node:
        bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        if not bundled.is_file():pytest.skip('Node required for frontend helper test')
        node=str(bundled)
    result=subprocess.run([node,str(Path(__file__).resolve().parents[2]/'tests/web/js/run_jump.mjs')],capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
