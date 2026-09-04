"""Verdict and authority paths the docs call verified, each exercised end to end."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import nemisis.cli as cli
from nemisis.crash_fixture import (
    ATOMIC_REF,
    BUGGY_REF,
    MISLEADING_GREEN_REF,
    SCENARIO_ID,
    load_issue,
)
from nemisis.crash_models import (
    CrashObservation,
    CrashVerdict,
    ExecutionStatus,
    WorldRole,
)
from nemisis.crashcheck import (
    CrashCheckError,
    _audited_contract,
    _seal_capsule,
    check,
    initialize,
    replay,
)

TARGET = "app.credits:apply_credit"

OVER_CREDITING = '''"""Over-crediting handler: the invariant negative control."""


def apply_credit(store, event):
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    store.mark_processed(event["event_id"])
'''

THREE_ARGUMENT = """def apply_credit(store, event, extra=None):
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""


def _tree(tmp_path: Path, name: str, handler_source: str) -> Path:
    root = tmp_path / name
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text('"""app"""\n', encoding="utf-8")
    (root / "app" / "credits.py").write_text(handler_source, encoding="utf-8")
    return root


def _draft_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    issue = workspace / "issue.md"
    issue.write_text(load_issue() + "\nLocal contract.\n", encoding="utf-8")
    return initialize(issue, TARGET, BUGGY_REF, SCENARIO_ID)


def test_over_crediting_candidate_fails_the_invariant_and_proves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "over-crediting", OVER_CREDITING)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "invariant failed" in result.summary
    candidate_attempts = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert len(candidate_attempts) == 5
    assert {a.observation for a in candidate_attempts} == {CrashObservation.INVARIANT_FAILED}
    assert all(a.execution_status is ExecutionStatus.COMPLETED for a in candidate_attempts)
    final = candidate_attempts[0].final_snapshot
    assert final is not None and final.account_balance_cents == 7_500
    assert cli._exit_code(result.verdict) == 2


def test_replay_base_role_can_reproduce_but_never_prove_a_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    capsule = _seal_capsule(_audited_contract())

    reproduced = replay(capsule, BUGGY_REF, role="base")
    assert reproduced.verdict is CrashVerdict.BUG_REPRODUCED
    assert cli._exit_code(reproduced.verdict) == 1

    not_reproduced = replay(capsule, ATOMIC_REF, role="base")
    assert not_reproduced.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "did not reproduce" in not_reproduced.summary
    assert all(a.observation is CrashObservation.EXACTLY_ONCE for a in not_reproduced.attempts)

    still_broken = replay(capsule, MISLEADING_GREEN_REF, role="candidate")
    assert still_broken.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES


def test_same_ref_for_two_roles_is_refused_with_a_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    with pytest.raises(CrashCheckError, match="same source ref and tree"):
        check(BUGGY_REF, BUGGY_REF, SCENARIO_ID, mode="local")
    with pytest.raises(CrashCheckError, match="same source ref and tree"):
        check(BUGGY_REF, ATOMIC_REF, SCENARIO_ID, corrected=ATOMIC_REF, mode="local")


def test_symlinked_output_dir_still_publishes_the_finished_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nemisis",
            "check",
            "--base",
            BUGGY_REF,
            "--candidate",
            MISLEADING_GREEN_REF,
            "--output-dir",
            str(link / "out"),
        ],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    out = capsys.readouterr().out
    assert "verdict: PATCH_FAILED_STILL_REPRODUCES" in out
    assert list((real / "out" / "runs").glob("*/manifest.json"))
