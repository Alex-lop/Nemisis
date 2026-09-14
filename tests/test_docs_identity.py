"""Exact identities quoted as current in the ledgers must equal the installed engine."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from nemisis.crashcheck import engine_code_digest

ROOT = Path(__file__).parents[1]
EXAMPLE_WORKFLOW = ROOT / ".github/examples/crashcheck.yml"


def _quoted_current_digest(document: Path, marker: str) -> str:
    text = document.read_text(encoding="utf-8")
    match = re.search(marker + r"[^\n]*?`([0-9a-f]{64})`", text)
    assert match is not None, f"{document.name} no longer quotes a current engine digest"
    return match.group(1)


def test_status_and_proof_quote_the_installed_engine_digest() -> None:
    current = engine_code_digest()
    assert (
        _quoted_current_digest(ROOT / "docs/STATUS.md", r"Current tree:\n\n- engine code digest: ")
        == current
    )
    assert (
        _quoted_current_digest(ROOT / "docs/PROOF.md", r"the current engine\ncode digest is ")
        == current
    )


def test_example_workflow_pins_the_reviewed_action_commit_named_in_status() -> None:
    """Anyone who copies the example gets the engine at this SHA, so it must not rot silently."""
    pinned = re.findall(
        r"uses: Alex-lop/Nemisis@([0-9a-f]{40})\n", EXAMPLE_WORKFLOW.read_text(encoding="utf-8")
    )
    assert len(pinned) == 1, "the example must pin the Nemisis action to exactly one full commit"
    status = (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
    match = re.search(r"reviewed action pin: `([0-9a-f]{40})`", status)
    assert match is not None, "docs/STATUS.md no longer names a reviewed action pin"
    assert pinned[0] == match.group(1), (
        "the example workflow and docs/STATUS.md disagree about the reviewed action pin"
    )


def _git(*args: str) -> str:
    completed = subprocess.run(["git", *args], check=True, capture_output=True, text=True, cwd=ROOT)
    return completed.stdout.strip()


def test_the_pinned_engine_is_the_engine_where_this_branch_left_main() -> None:
    """The pin must not rot: `src/nemisis` at the pinned commit is `src/nemisis` at the commit
    where this branch left `main` (on `main` itself, HEAD). An engine change on a branch stays
    green while the branch is open; `main` goes red the moment an engine change lands without the
    pin following it. `.github/workflows/pin-bump.yml` moves the pin; this test says so when that
    workflow is off. A shallow clone cannot answer the question and fails here, never skips."""
    pinned = re.findall(
        r"uses: Alex-lop/Nemisis@([0-9a-f]{40})\n", EXAMPLE_WORKFLOW.read_text(encoding="utf-8")
    )
    assert len(pinned) == 1
    pin = pinned[0]
    try:
        base = _git("merge-base", "HEAD", "origin/main")
        pinned_engine = _git("rev-parse", f"{pin}:src/nemisis")
        base_engine = _git("rev-parse", f"{base}:src/nemisis")
    except subprocess.CalledProcessError as error:
        raise AssertionError(
            "git could not resolve the pinned commit or origin/main; fetch the full history "
            "(fetch-depth: 0 in CI, `git fetch --unshallow origin` locally): "
            f"{error.stderr.strip()}"
        ) from error
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", pin, base], cwd=ROOT, check=False
    )
    assert ancestor.returncode == 0, (
        f"the pinned commit {pin[:12]} is not an ancestor of {base[:12]}"
    )
    assert pinned_engine == base_engine, (
        f"the example pins {pin[:12]}, whose src/nemisis tree ({pinned_engine[:12]}) differs from "
        f"the tree at {base[:12]} ({base_engine[:12]}), where this branch left main: the pin has "
        "rotted and pin-bump.yml has not moved it"
    )
