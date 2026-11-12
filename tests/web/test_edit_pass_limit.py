import shutil,subprocess
from pathlib import Path
import pytest


@pytest.mark.req('EDIT-LOOP-REVIEW')
def test_edit_pass_limit_is_remembered_per_story():
    node=shutil.which('node')
    if not node:
        bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        if not bundled.is_file():pytest.skip('Node required for frontend helper test')
        node=str(bundled)
    result=subprocess.run([node,str(Path(__file__).resolve().parents[2]/'tests/web/js/edit-pass-limit.mjs')],capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
