from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_nix_files_exist() -> None:
    assert (ROOT / "flake.nix").is_file(), "flake.nix повинен існувати"
    assert (ROOT / "flake.lock").is_file(), "flake.lock повинен існувати"
    assert (ROOT / "shell.nix").is_file(), "shell.nix повинен існувати"
    assert (ROOT / ".envrc").is_file(), ".envrc повинен існувати"
    assert (ROOT / "scripts/start.sh").is_file(), "scripts/start.sh повинен існувати"


def test_gitignore_contains_nix_entries() -> None:
    gitignore_text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".direnv/" in gitignore_text
    assert "result" in gitignore_text


def test_start_sh_syntax_and_default_port() -> None:
    start_sh = ROOT / "scripts/start.sh"
    start_sh_text = start_sh.read_text(encoding="utf-8")
    assert "PORT=8760" in start_sh_text, "Порт за замовчуванням у scripts/start.sh має бути 8760"
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash не знайдено в PATH")
    res = subprocess.run([bash, "-n", str(start_sh)], capture_output=True, text=True)
    assert res.returncode == 0, f"Синтаксична помилка у start.sh: {res.stderr}"


def test_nix_flake_metadata_if_installed() -> None:
    nix = shutil.which("nix")
    if not nix:
        pytest.skip("nix не знайдено в PATH")
    res = subprocess.run(
        [nix, "flake", "metadata", "--no-update-lock-file"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"nix flake metadata failed: {res.stderr}"


def test_nix_documentation_and_flake_contract() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Швидкий запуск через Nix" not in readme_text, "README.md не повинен містити окремого розділу про Nix"
    assert "CONTRIBUTING.md" in readme_text
    assert "неофіційно, без гарантій" in readme_text

    contributing_text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "Офіційно підтримується лише Windows; Linux/macOS через Nix — неофіційно, без гарантій" in contributing_text
    assert "nix develop" in contributing_text
    assert "nix run" in contributing_text

    flake_text = (ROOT / "flake.nix").read_text(encoding="utf-8")
    assert "apps.default" in flake_text, "flake.nix повинен визначати apps.default"
    assert "--no-deps" in flake_text, "flake.nix має встановлювати пакет через pip install --no-deps"
    assert "LD_LIBRARY_PATH" in flake_text, "flake.nix має налаштовувати LD_LIBRARY_PATH на Linux"
    assert "pyproject.toml" in flake_text, "flake.nix має перевіряти наявність pyproject.toml"
