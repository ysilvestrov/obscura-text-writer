"""The pre-push hook refuses a push into a branch whose pull request is no longer open."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".githooks" / "pre-push"
SH = shutil.which("sh")
SHA = "1" * 40
ZERO = "0" * 40

FAKE_GH = """#!/bin/sh
[ -n "$FAKE_GH_LOG" ] && echo "$*" >> "$FAKE_GH_LOG"
[ "$FAKE_GH_FAIL" = 1 ] && exit 1
echo "$FAKE_GH_STATES"
"""

pytestmark = pytest.mark.skipif(SH is None, reason="POSIX sh is not available")


def run(tmp_path, *, states="", fail=False, refs=None, url="https://github.com/o/r.git",
        with_gh=True, extra_env=None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    if with_gh:
        (bin_dir / "gh").write_text(FAKE_GH, encoding="utf-8", newline="\n")
        os.chmod(bin_dir / "gh", 0o755)
    log = tmp_path / "gh.log"
    env = {
        "PATH": str(bin_dir) + os.pathsep + str(Path(SH).parent),
        "FAKE_GH_STATES": states,
        "FAKE_GH_FAIL": "1" if fail else "0",
        "FAKE_GH_LOG": str(log),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        **(extra_env or {}),
    }
    if refs is None:
        refs = f"refs/heads/topic {SHA} refs/heads/topic {ZERO}\n"
    result = subprocess.run(
        [SH, str(HOOK), "origin", url], input=refs, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    calls = log.read_text(encoding="utf-8") if log.exists() else ""
    return result, calls


def test_push_to_branch_with_merged_pr_is_refused(tmp_path):
    result, calls = run(tmp_path, states="MERGED")
    assert result.returncode == 1
    assert "topic" in result.stderr and "origin/main" in result.stderr
    assert "--head topic" in calls


def test_push_to_branch_with_closed_pr_is_refused(tmp_path):
    result, _ = run(tmp_path, states="CLOSED")
    assert result.returncode == 1


def test_push_to_branch_with_open_pr_passes(tmp_path):
    result, _ = run(tmp_path, states="OPEN")
    assert result.returncode == 0, result.stderr


def test_reused_branch_name_with_new_open_pr_passes(tmp_path):
    result, _ = run(tmp_path, states="MERGED OPEN")
    assert result.returncode == 0, result.stderr


def test_branch_without_pr_passes(tmp_path):
    result, _ = run(tmp_path, states="")
    assert result.returncode == 0, result.stderr


def test_deleting_a_merged_branch_passes_without_asking(tmp_path):
    result, calls = run(tmp_path, states="MERGED",
                        refs=f"(delete) {ZERO} refs/heads/topic {SHA}\n")
    assert result.returncode == 0, result.stderr
    assert calls == ""


def test_tags_are_not_checked(tmp_path):
    result, calls = run(tmp_path, states="MERGED",
                        refs=f"refs/tags/v1 {SHA} refs/tags/v1 {ZERO}\n")
    assert result.returncode == 0
    assert calls == ""


def test_one_merged_branch_among_several_refuses_the_push(tmp_path):
    refs = (f"refs/heads/a {SHA} refs/heads/a {ZERO}\n"
            f"refs/heads/b {SHA} refs/heads/b {ZERO}\n")
    result, calls = run(tmp_path, states="MERGED", refs=refs)
    assert result.returncode == 1
    assert "--head a" in calls and "--head b" in calls


def test_unreachable_github_warns_and_lets_the_push_through(tmp_path):
    result, _ = run(tmp_path, fail=True)
    assert result.returncode == 0
    assert "not checked" in result.stderr


def test_missing_gh_warns_and_lets_the_push_through(tmp_path):
    result, _ = run(tmp_path, with_gh=False)
    assert result.returncode == 0
    assert "not checked" in result.stderr


def test_other_remotes_are_not_checked(tmp_path):
    result, calls = run(tmp_path, states="MERGED", url="C:/backup/repo.git")
    assert result.returncode == 0
    assert calls == ""


def test_explicit_override_lets_the_push_through(tmp_path):
    result, _ = run(tmp_path, states="MERGED", extra_env={"ALLOW_PUSH_TO_MERGED": "1"})
    assert result.returncode == 0


@pytest.mark.parametrize("url", [
    "https://github.com/Owner/repo.git",
    "https://github.com/Owner/repo",
    "git@github.com:Owner/repo.git",
    "ssh://git@github.com/Owner/repo.git",
])
def test_the_destination_repository_is_the_one_asked(tmp_path, url):
    _, calls = run(tmp_path, states="OPEN", url=url)
    assert "--repo Owner/repo " in calls


def test_only_pull_requests_from_the_destination_owner_count(tmp_path):
    _, calls = run(tmp_path, states="OPEN", url="https://github.com/Owner/repo.git")
    assert "headRepositoryOwner" in calls
    assert '"owner"' in calls  # compared in lower case


def test_unrecognised_github_address_warns_and_lets_the_push_through(tmp_path):
    result, calls = run(tmp_path, states="MERGED", url="https://github.com/only-one-part")
    assert result.returncode == 0
    assert "not checked" in result.stderr
    assert calls == ""
