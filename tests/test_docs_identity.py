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


# What `uses: Alex-lop/Nemisis@<sha>` actually runs: the engine, the action's contract, and the
# locked environment it installs. A pin that lags any of these hands a copier a different tool.
ACTION_RUNTIME = ("src/nemisis", "action.yml", "pyproject.toml", "uv.lock")


def test_the_pinned_action_is_main_s_action() -> None:
    """The pin must not rot. Everywhere: the pinned commit is an ancestor of HEAD, so it lies in
    this history and not on a stray branch. On `main` itself (HEAD is `origin/main`): the engine,
    `action.yml`, `pyproject.toml`, and `uv.lock` at the pinned commit are byte-identical to
    HEAD's, so `main` goes red the moment any of them changes without the pin following. A branch
    is not held to that, because a branch cannot pin a commit `main` does not have yet; an engine
    pull request may carry its own bump (pin its last engine commit) or leave the bump to
    `.github/workflows/pin-bump.yml`, which opens it after the merge. A shallow clone cannot
    answer the question and fails here; it never skips."""
    pinned = re.findall(
        r"uses: Alex-lop/Nemisis@([0-9a-f]{40})\n", EXAMPLE_WORKFLOW.read_text(encoding="utf-8")
    )
    assert len(pinned) == 1
    pin = pinned[0]
    try:
        head = _git("rev-parse", "HEAD")
        main = _git("rev-parse", "origin/main")
        _git("cat-file", "-e", f"{pin}^{{commit}}")
    except subprocess.CalledProcessError as error:
        raise AssertionError(
            "git could not resolve HEAD, origin/main, or the pinned commit; fetch the full "
            "history (fetch-depth: 0 in CI; locally "
            "`git fetch --unshallow origin +refs/heads/main:refs/remotes/origin/main`): "
            f"{error.stderr.strip()}"
        ) from error
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", pin, head], cwd=ROOT, check=False
    )
    assert ancestor.returncode == 0, f"the pinned commit {pin[:12]} is not in HEAD's history"
    if head != main:
        return  # a branch: the strict comparison belongs to main, where the bot keeps it true
    differing = [
        path
        for path in ACTION_RUNTIME
        if _git("rev-parse", f"{pin}:{path}") != _git("rev-parse", f"{head}:{path}")
    ]
    assert not differing, (
        f"the example pins {pin[:12]}, but {', '.join(differing)} changed on main since then: "
        "the pin has rotted and pin-bump.yml has not moved it"
    )
