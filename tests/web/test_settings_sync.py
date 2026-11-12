"""MCP-BRIDGE package 5: the open settings page notices changes made elsewhere (S37)."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.req('MCP-BRIDGE')
def test_settings_page_decides_on_outside_changes():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, str(root / 'tests/web/js/settings_sync.mjs')], capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr
