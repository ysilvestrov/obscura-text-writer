import shutil
import subprocess
from pathlib import Path

import pytest


def test_role_profiles_preview_dirty_conflict_and_apply():
    node=shutil.which('node')
    if not node:pytest.skip('Node потрібен для перевірки ES module')
    root=Path(__file__).resolve().parents[2]
    result=subprocess.run([node,str(root/'tests/web/js/role_profiles.mjs'),str(root)],capture_output=True,encoding='utf-8',errors='replace',timeout=15)
    assert result.returncode==0,result.stderr
