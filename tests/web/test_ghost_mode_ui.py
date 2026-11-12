"""#55: the Ghost Mode session model (node ES module test)."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_ghost_session_states_storage_and_stats():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, str(root / 'tests/web/js/ghost_session.mjs')], capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.req('MCP-BRIDGE')
def test_ghost_link_parsing_and_refusals():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node потрібен для перевірки ES module')
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([node, str(root / 'tests/web/js/ghost_link.mjs')], capture_output=True, encoding='utf-8', errors='replace', timeout=15)
    assert result.returncode == 0, result.stderr
