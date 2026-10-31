"""Verify checked-in editor assets without Node or installed JS dependencies."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src/storygen/web/static"


def check_bundle(root=ROOT):
    static = root / "src/storygen/web/static"
    manifest = json.loads((static / "editor-bundle.json").read_text(encoding="utf-8"))
    assert manifest["version"] == 1, "Unknown bundle manifest"
    actual_sources = {path.relative_to(root).as_posix() for path in (root / "frontend/src").glob("*.js")}
    listed_sources = {path for path in manifest["sources"] if path.startswith("frontend/src/")}
    assert actual_sources == listed_sources, "Editor source list changed; rebuild frontend"
    for path, expected in manifest["sources"].items():
        content = (root / path).read_bytes().replace(b"\r\n", b"\n")
        assert sha256(content).hexdigest() == expected, f"Editor source changed: {path}; rebuild frontend"
    for path, expected in manifest["assets"].items():
        assert sha256((static / path).read_bytes()).hexdigest() == expected, f"Editor asset changed: {path}"
    assert manifest["licenses"], "No bundled dependency licenses"
    for item in manifest["licenses"]:
        assert sha256((static / item["path"]).read_bytes()).hexdigest() == item["sha256"], f"License changed: {item['name']}"
    return manifest


if __name__ == "__main__":
    check_bundle()
    print("Editor bundle: source, lockfile, assets and licenses match")
