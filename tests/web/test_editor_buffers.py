import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.parametrize('scenario',['titles','refresh','plan','prose','draft','draft-clean','draft-dirty','draft-history','memory-clean','memory-dirty','memory-history'])
def test_editor_buffers_keep_revision_and_typing_during_save(scenario):
    node=shutil.which('node')
    if node is None:pytest.skip('Node is required only for browser-module unit tests')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/editor_regressions.mjs'),scenario,str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
