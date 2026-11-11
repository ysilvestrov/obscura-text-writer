"""MCP-BRIDGE (#105): the open workspace picks up scene changes made elsewhere without losing unsaved text."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'src/storygen/web/static'


@pytest.mark.req('MCP-BRIDGE')
def test_scene_sync_rules():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    result = subprocess.run([node, str(ROOT / 'tests/web/js/scene_sync.mjs'), str(ROOT)],
                            capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr
