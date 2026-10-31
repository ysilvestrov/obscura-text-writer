"""Pure Node checks of the shipped bridge; no npm install/network at test time."""
from pathlib import Path
import shutil
import subprocess
import importlib.util

import pytest

ROOT = Path(__file__).resolve().parents[2]


def bundle_checker():
    spec = importlib.util.spec_from_file_location("check_editor_bundle", ROOT / "scripts/check_editor_bundle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check_bundle


def test_markdown_source_bridge():
    node = shutil.which("node")
    if not node:
        bundled = Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        if not bundled.is_file():pytest.skip('Node is required only for bridge development tests')
        node = str(bundled)
    result = subprocess.run(
        [node, str(ROOT / "tests/web/js/markdown-bridge.mjs")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_editor_bundle_matches_sources_and_licenses():
    manifest = bundle_checker()()
    assert {item["name"] for item in manifest["licenses"]} >= {
        "prosemirror-model", "prosemirror-view", "mdast-util-from-markdown", "mdast-util-to-markdown",
    }


def test_editor_bundle_rejects_changed_source(tmp_path):
    shutil.copytree(ROOT / "frontend/src", tmp_path / "frontend/src")
    for name in ("package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "build.mjs"):
        shutil.copy2(ROOT / "frontend" / name, tmp_path / "frontend" / name)
    target = tmp_path / "src/storygen/web/static"
    target.mkdir(parents=True)
    shutil.copy2(ROOT / "src/storygen/web/static/editor-bundle.json", target)
    (tmp_path / "frontend/src/source-map.js").write_text("changed", encoding="utf-8")
    with pytest.raises(AssertionError, match="source changed"):
        bundle_checker()(tmp_path)
