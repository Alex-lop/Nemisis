"""The README's "Point it at your code" sequence, run literally against a real Git repository.

``init`` (draft) -> ``init --accept-contract <digest>`` -> ``check --base main --candidate HEAD
--scenario .nemisis/config.json``, through the console entry point in a subprocess, with the
printed digest parsed from stdout rather than hardcoded, and the exit code and verdict asserted.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from nemisis.crash_fixture import ATOMIC_REF, BUGGY_REF, MISLEADING_GREEN_REF, materialize_fixture

CONTRACT_LINE = re.compile(r"^contract: ([0-9a-f]{64})$", re.MULTILINE)
STATUS_LINE = re.compile(r"^status: (DRAFT|ACCEPTED)$", re.MULTILINE)


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    ).stdout.strip()


def _nemisis(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the console entry point exactly as an installed ``nemisis`` would, from the repo root."""
    environment = {
        name: value
        for name, value in os.environ.items()
        if name not in {"GITHUB_EVENT_NAME", "GITHUB_EVENT_PATH", "NEMISIS_ARTIFACT_ROOT"}
    }
    return subprocess.run(
        [sys.executable, "-c", "from nemisis.cli import main; main()", *args],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _status(output: str) -> str:
    match = STATUS_LINE.search(output)
    assert match is not None, output
    return match.group(1)


def _handler_from(ref: str, scratch: Path) -> Path:
    return materialize_fixture(ref, scratch).path / "app/credits.py"


def test_readme_sequence_runs_against_a_real_git_repository(tmp_path: Path) -> None:
    repository = materialize_fixture(BUGGY_REF, tmp_path / "repo").path
    (repository / "issue.md").write_text(
        "# Duplicate account credit after retry\n\nMake apply_credit idempotent by event ID.\n",
        encoding="utf-8",
    )
    _git(repository, "init", "-q", "-b", "main")
    _git(repository, "config", "user.email", "dev@example.invalid")
    _git(repository, "config", "user.name", "Developer")
    _git(repository, "add", ".")
    _git(repository, "commit", "-q", "-m", "buggy handler")
    init = ("init", "--issue", "issue.md", "--target", "app.credits:apply_credit", "--base", "main")

    drafted = _nemisis(repository, *init)
    assert drafted.returncode == 0, drafted.stderr
    digest = CONTRACT_LINE.search(drafted.stdout)
    assert digest is not None, drafted.stdout
    assert _status(drafted.stdout) == "DRAFT"

    accepted = _nemisis(repository, *init, "--accept-contract", digest.group(1))
    assert accepted.returncode == 0, accepted.stderr
    assert _status(accepted.stdout) == "ACCEPTED"
    _git(repository, "add", ".nemisis/config.json")
    _git(repository, "commit", "-q", "-m", "commit the accepted CrashCheck contract on the base")

    # The atomic fix on a branch: HEAD is the candidate, main is the base.
    _git(repository, "checkout", "-q", "-b", "fix")
    shutil.copy2(_handler_from(ATOMIC_REF, tmp_path / "atomic"), repository / "app/credits.py")
    _git(repository, "commit", "-q", "-am", "atomic credit and marker")
    check = ("check", "--base", "main", "--candidate", "HEAD", "--scenario", ".nemisis/config.json")

    proven = _nemisis(repository, *check)
    assert proven.returncode == 0, proven.stdout + proven.stderr
    assert "verdict: FIX_PROVEN_FOR_THIS_CAPSULE" in proven.stdout
    assert f"source: main -> {_git(repository, 'rev-parse', 'main')}" in proven.stdout
    assert f"source: HEAD -> {_git(repository, 'rev-parse', 'HEAD')}" in proven.stdout

    # The agent's green patch on another branch: same base, same contract, exit 1.
    _git(repository, "checkout", "-q", "-b", "green", "main")
    shutil.copy2(
        _handler_from(MISLEADING_GREEN_REF, tmp_path / "green"), repository / "app/credits.py"
    )
    _git(repository, "commit", "-q", "-am", "rewrite the handler without moving the crash window")

    failed = _nemisis(repository, *check)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "verdict: PATCH_FAILED_STILL_REPRODUCES" in failed.stdout
    assert len(list((repository / ".nemisis" / "runs").glob("*/manifest.json"))) == 2
