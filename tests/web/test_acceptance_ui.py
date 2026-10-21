import shutil
import subprocess
from pathlib import Path
import pytest


def test_acceptance_ui_guards_preview_commit_and_conflict():
    node=shutil.which('node')
    if not node:pytest.skip('Node потрібен для перевірки браузерного модуля')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/acceptance_regressions.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
