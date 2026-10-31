import shutil
import subprocess
from pathlib import Path
import pytest


def test_comment_mapping_and_document_history():
    node=shutil.which('node')
    if not node:pytest.skip('Node is required only for browser-module tests')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/comment-state.mjs')],capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
