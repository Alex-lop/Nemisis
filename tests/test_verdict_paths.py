"""Verdict and authority paths the docs call verified, each exercised end to end."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import nemisis.cli as cli
import nemisis.crashcheck as crashcheck_module
from nemisis.crash_fixture import (
    ATOMIC_REF,
    BUGGY_REF,
    MISLEADING_GREEN_REF,
    SCENARIO_ID,
    load_issue,
)
from nemisis.crash_models import (
    AnchorResolutionStatus,
    CrashObservation,
    CrashVerdict,
    ExecutionStatus,
    RetryContract,
    WorldRole,
)
from nemisis.crashcheck import (
    CrashCheckError,
    _audited_contract,
    _seal_capsule,
    accept_contract,
    check,
    initialize,
    replay,
)
from nemisis.hashing import canonical_json
from nemisis.models import TruthLabel

TARGET = "app.credits:apply_credit"

OVER_CREDITING = '''"""Over-crediting handler: the invariant negative control."""


def apply_credit(store, event):
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    store.mark_processed(event["event_id"])
'''

MARK_THEN_CREDIT = """def apply_credit(store, event):
    if store.processed(event["event_id"]):
        return
    store.mark_processed(event["event_id"])
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
"""

CREDIT_NEVER_MARKS = """def apply_credit(store, event):
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
"""

DIRECT_SQL_EFFECT = """import sqlite3


def apply_credit(store, event):
    if store.processed(event["event_id"]):
        return
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE accounts SET balance_cents = balance_cents + ? WHERE account_id = ?",
            (event["amount_cents"], event["account_id"]),
        )
        connection.execute(
            "INSERT INTO credit_ledger(event_id, account_id, amount_cents) VALUES (?, ?, ?)",
            (event["event_id"], event["account_id"], event["amount_cents"]),
        )
        connection.commit()
    store.mark_processed(event["event_id"])
"""

DRIFT_AFTER_LAST_COMMIT = """import sqlite3


def apply_credit(store, event):
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute(
            "INSERT INTO credit_ledger(event_id, account_id, amount_cents) VALUES (?, ?, ?)",
            (event["event_id"], event["account_id"], 1),
        )
"""

LEFTOVER_CREDIT = """def apply_credit(store, event):
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
"""

CHATTY_LOGGER = """import sys


def apply_credit(store, event):
    for line in range(6000):
        print("debug: about to credit", line, event["event_id"])
        print("debug: still here", line, file=sys.stderr)
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
    for line in range(6000):
        print("debug: credited", line)
"""

AUDIT_FILE = """def apply_credit(store, event):
    with open("audit.log", "a", encoding="utf-8") as log:
        log.write(f"crediting {event['event_id']}\\n")
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

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


def test_over_crediting_candidate_is_a_failed_patch_not_missing_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "over-crediting", OVER_CREDITING)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN
    assert "$75.00 instead of $25.00" in result.summary
    assert "credited 3 times" in result.summary
    candidate_attempts = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert len(candidate_attempts) == 5
    assert {a.observation for a in candidate_attempts} == {CrashObservation.INVARIANT_FAILED}
    assert all(a.execution_status is ExecutionStatus.COMPLETED for a in candidate_attempts)
    final = candidate_attempts[0].final_snapshot
    assert final is not None and final.account_balance_cents == 7_500
    assert cli._exit_code(result.verdict) == 1


def test_mark_then_credit_passes_the_boundary_and_fails_the_commit_sweep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The false negative that motivated the sweep: green at the base's kill point, and it loses
    the credit when killed one commit earlier."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "mark-then-credit", MARK_THEN_CREDIT)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, corrected=ATOMIC_REF, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN
    assert "commit 1 of 2 (mark_processed)" in result.summary
    assert "$0.00 instead of $25.00" in result.summary
    assert "never credited" in result.summary
    boundary = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert {a.observation for a in boundary} == {CrashObservation.EXACTLY_ONCE}
    sweeps = {sweep.role: sweep for sweep in result.sweeps}
    candidate_sweep = sweeps[WorldRole.CANDIDATE]
    assert candidate_sweep.census.first_delivery_operations == ("mark_processed", "credit")
    assert [a.observation for a in candidate_sweep.attempts] == [
        CrashObservation.INVARIANT_FAILED,
        CrashObservation.EXACTLY_ONCE,
    ]
    assert [a.kill_after_commit for a in candidate_sweep.attempts] == [1, 2]
    assert sweeps[WorldRole.CORRECTED].observation is CrashObservation.EXACTLY_ONCE
    assert sweeps[WorldRole.CORRECTED].census.first_delivery_operations == ("credit_and_mark",)
    assert cli._exit_code(result.verdict) == 1
    report = (tmp_path / "artifacts" / result.artifacts["report"]).read_text(encoding="utf-8")
    assert "Commit sweep · candidate" in report
    assert "after commit 1" in report


def test_leftover_credit_after_the_atomic_call_is_a_duplicate_not_a_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red-team finding: this handler double-credits on every delivery. Before the receipts
    validated relationally, the real evidence was rejected by a fixture-shaped validator and the
    run said "attempt orchestration failed (ValidationError)" instead of naming the duplicate."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "leftover-credit", LEFTOVER_CREDIT)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    boundary = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert {a.observation for a in boundary} == {CrashObservation.DUPLICATE_EFFECT}
    assert all(a.execution_status is ExecutionStatus.COMPLETED for a in boundary)
    checkpoint = boundary[0].checkpoint_snapshot
    assert checkpoint is not None and checkpoint.event_marker_count == 1
    assert cli._exit_code(result.verdict) == 1


@pytest.mark.parametrize(
    ("name", "source"),
    [("chatty-logger", CHATTY_LOGGER), ("audit-file", AUDIT_FILE)],
)
def test_correct_handlers_with_noisy_side_channels_are_still_proven(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, source: str
) -> None:
    """Red-team false fails: a handler that logs more than one pipe buffer used to block on a
    full pipe and time out; one that appends a relative audit file used to dirty the bound tree
    because the worker ran inside it. Neither touches the money."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, name, source)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE, result.summary
    assert cli._exit_code(result.verdict) == 0
    assert not list(candidate.rglob("audit.log"))


def test_candidate_that_never_marks_still_duplicates_and_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two credits are a duplicate whether or not the marker ever landed."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "never-marks", CREDIT_NEVER_MARKS)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    candidate_attempts = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert {a.observation for a in candidate_attempts} == {CrashObservation.DUPLICATE_EFFECT}
    final = candidate_attempts[0].final_snapshot
    assert final is not None
    assert (final.account_balance_cents, final.event_ledger_count, final.event_marker_count) == (
        5_000,
        2,
        0,
    )
    assert cli._exit_code(result.verdict) == 1


@pytest.mark.parametrize(
    ("name", "source", "detail"),
    [
        ("direct-sql", DIRECT_SQL_EFFECT, "mark_processed reported, but the database moved"),
        ("drift", DRIFT_AFTER_LAST_COMMIT, "after its last reported commit"),
    ],
)
def test_effects_committed_outside_the_trusted_store_are_an_integrity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, source: str, detail: str
) -> None:
    """A handler that moves money through its own connection cannot earn a verdict.

    Before this check, such a handler was PROVEN: the controller only kills at store commits, so
    the real crash window (between the direct write and the marker) was never exercised.
    """
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, name, source)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert result.integrity_status.value == "INVALID"
    assert "outside the trusted store" in result.summary
    assert detail in result.summary
    candidate_attempts = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert len(candidate_attempts) == 5
    assert all(a.execution_status is ExecutionStatus.INTEGRITY_ERROR for a in candidate_attempts)
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


def test_check_refuses_a_draft_contract_and_a_contract_for_another_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    config = _draft_config(tmp_path, monkeypatch)
    assert json.loads(config.read_bytes())["status"] == "DRAFT"

    with pytest.raises(CrashCheckError, match="contract is DRAFT"):
        check(BUGGY_REF, MISLEADING_GREEN_REF, config, mode="local")

    accept_contract(json.loads(config.read_bytes())["contract"]["digest"], config)
    with pytest.raises(CrashCheckError, match="originating base digest differs"):
        check(MISLEADING_GREEN_REF, ATOMIC_REF, config, mode="local")
    assert not (tmp_path / "artifacts").exists()


def test_accept_contract_refuses_a_wrong_digest_and_a_second_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _draft_config(tmp_path, monkeypatch)
    before = config.read_bytes()

    with pytest.raises(CrashCheckError, match="does not match the current draft"):
        accept_contract("0" * 64, config)
    assert config.read_bytes() == before

    accepted = accept_contract(json.loads(before)["contract"]["digest"], config)
    assert accepted.accepted and accepted.truth_label is TruthLabel.LOCAL
    with pytest.raises(CrashCheckError, match="already ACCEPTED"):
        accept_contract(accepted.digest, config)
    with pytest.raises(CrashCheckError, match="already ACCEPTED"):
        accept_contract(json.loads(before)["contract"]["digest"], config)


def test_exported_capsule_refuses_a_substituted_accepted_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.chdir(tmp_path)
    audited = _audited_contract()
    capsule = _seal_capsule(audited)
    other = RetryContract.with_digest(
        **audited.model_dump(mode="python", exclude={"digest", "accepted", "truth_label"})
        | {"issue_digest": "e" * 64},
        accepted=True,
        truth_label=TruthLabel.LOCAL,
    )
    repro = tmp_path / "repro"
    repro.mkdir()
    (repro / "capsule.json").write_bytes(canonical_json(capsule) + b"\n")
    (repro / "contract.json").write_bytes(canonical_json(other) + b"\n")

    with pytest.raises(CrashCheckError, match="unaccepted or has another digest"):
        replay(repro / "capsule.json", ATOMIC_REF, role="corrected")

    (repro / "capsule.json").write_bytes(canonical_json(_seal_capsule(other)) + b"\n")
    (repro / "contract.json").unlink()
    with pytest.raises(CrashCheckError, match="not the audited or accepted local contract"):
        replay(repro / "capsule.json", ATOMIC_REF, role="corrected")


def test_replay_live_mode_is_blocked_without_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("NEBIUS_API_KEY", "CONTREE_PROFILE", "CONTREE_HOME", "NEMISIS_CONTREE_ROOT_IMAGE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-config"))
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = replay(_seal_capsule(_audited_contract()), ATOMIC_REF, role="corrected", mode="live")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert result.transport is TruthLabel.LIVE
    assert result.execution_status is ExecutionStatus.UNSUPPORTED
    assert "Local execution was not substituted" in result.summary
    assert result.attempts[0].spawns == ()


def test_base_that_does_not_reproduce_publishes_incomplete_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    original = crashcheck_module._confirmed_observation

    def base_never_reproduces(attempts: tuple[object, ...], capsule: object) -> CrashObservation:
        if attempts and getattr(attempts[0], "role", None) is WorldRole.BASE:
            return CrashObservation.NOT_OBSERVED
        return original(attempts, capsule)  # type: ignore[arg-type]

    monkeypatch.setattr(crashcheck_module, "_confirmed_observation", base_never_reproduces)

    result = check(BUGGY_REF, MISLEADING_GREEN_REF, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "did not reproduce in five fresh worlds" in result.summary
    assert {a.role for a in result.attempts} == {WorldRole.BASE}


def test_failed_corrected_control_withholds_the_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY_REF, ATOMIC_REF, SCENARIO_ID, corrected=MISLEADING_GREEN_REF, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "corrected control did not prove" in result.summary
    by_role = {
        role: {a.observation for a in result.attempts if a.role is role} for role in WorldRole
    }
    assert by_role[WorldRole.CANDIDATE] == {CrashObservation.EXACTLY_ONCE}
    assert by_role[WorldRole.CORRECTED] == {CrashObservation.DUPLICATE_EFFECT}


def test_three_argument_handler_is_an_invalid_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "three-argument", THREE_ARGUMENT)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    receipt = result.anchor_resolutions[0]
    assert receipt.role is WorldRole.CANDIDATE
    assert receipt.status is AnchorResolutionStatus.INVALID_MATCH
    assert receipt.matched_paths == ("app/credits.py",)
    assert "candidate target mapping" in result.summary
    assert "(store, event)" in result.summary
    assert {a.role for a in result.attempts} == {WorldRole.BASE}


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
