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
    LEFTOVER_CREDIT_REF,
    MARK_FIRST_REF,
    MISLEADING_GREEN_REF,
    NEVER_MARKS_REF,
    RAW_SQL_REF,
    SCENARIO_ID,
    SHADOW_TABLE_REF,
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
from nemisis.scenarios.sqlite_credit_v1 import SCENARIO as CREDIT

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

MARK_THEN_ATOMIC = """def apply_credit(store, event):
    store.mark_processed(event["event_id"])
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
    assert final is not None and final.subject_total == 7_500
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


GUARDED_LEFTOVER_CREDIT = """def apply_credit(store, event):
    event_id = event["event_id"]
    if store.processed(event_id):
        return
    store.credit_and_mark(event["account_id"], event_id, event["amount_cents"])
    store.credit(event["account_id"], event_id, event["amount_cents"])
"""


def test_guarded_leftover_credit_is_caught_by_the_census_and_blamed_on_no_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red team, high severity at the baseline: the guard makes the boundary worlds pass (the kill
    lands inside credit_and_mark and the replay returns early), yet every crash-free delivery
    posts $50. The census sees it first, so the summary blames the handler, not a crash window."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "guarded-leftover", GUARDED_LEFTOVER_CREDIT)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    assert "with no crash at all" in result.summary
    assert "$50.00 instead of $25.00" in result.summary
    boundary = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert {a.observation for a in boundary} == {CrashObservation.EXACTLY_ONCE}
    sweep = result.sweeps[0]
    assert sweep.census.observation is CrashObservation.DUPLICATE_EFFECT
    assert sweep.census.first_delivery_operations == ("credit_and_mark", "credit")
    assert cli._exit_code(result.verdict) == 1


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


def test_a_chatty_correct_handler_is_still_proven(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red-team false fail: a handler that logs more than one pipe buffer used to block on a full
    pipe and time out. Output is drained now, and stdout is not durable state."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "chatty-logger", CHATTY_LOGGER)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE, result.summary
    assert cli._exit_code(result.verdict) == 0


INFLIGHT_FILE_GUARD = """import os


def apply_credit(store, event):
    event_id = event["event_id"]
    if store.processed(event_id):
        return
    inflight = "inflight-" + event_id
    if os.path.exists(inflight):
        return
    with open(inflight, "w") as handle:
        handle.write("x")
    store.credit_and_mark(event["account_id"], event_id, event["amount_cents"])
"""


@pytest.mark.parametrize(
    ("name", "source"),
    [("audit-file", AUDIT_FILE), ("inflight-guard", INFLIGHT_FILE_GUARD)],
)
def test_durable_files_beside_the_database_forfeit_the_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, source: str
) -> None:
    """Red team, round two: a dedup file written before the atomic call has a crash window (file
    written, credit not committed, redelivery skips) that no store-commit kill point can reach, and
    the sweep blessed it. Any file the handler writes beside the database now forfeits the verdict
    with a message that says why; an audit log pays the same price because the tool cannot tell
    them apart. The bound source tree is never touched either way."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, name, source)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "wrote durable entries outside the store" in result.summary
    assert "cannot be reached" in result.summary
    boundary = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert {a.execution_status for a in boundary} == {ExecutionStatus.UNSUPPORTED}
    assert not list(candidate.rglob("audit.log")) and not list(candidate.rglob("inflight-*"))
    assert cli._exit_code(result.verdict) == 2


MARK_ON_REDELIVERY = """def apply_credit(store, event):
    event_id = event["event_id"]
    if store.processed(event_id):
        return
    store.credit(event["account_id"], event_id, event["amount_cents"])
"""


def test_a_delivery_that_leaves_the_marker_for_later_fails_the_census(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red team, round two: a single no-crash delivery must already be exactly once. This handler
    credits and never marks, so it is caught at the boundary; the census rule is exercised directly
    on its receipts below."""
    from nemisis.crash_models import StateSnapshot, classify_delivery

    once = StateSnapshot.with_digest(
        subject_total=2500,
        event_effect_count=1,
        event_effect_total=2500,
        event_marker_count=1,
    )
    unmarked = StateSnapshot.with_digest(
        subject_total=2500,
        event_effect_count=1,
        event_effect_total=2500,
        event_marker_count=0,
    )
    assert classify_delivery(once, once, 2500, 0) is CrashObservation.EXACTLY_ONCE
    assert classify_delivery(unmarked, once, 2500, 0) is CrashObservation.INVARIANT_FAILED
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    result = check(BUGGY_REF, _tree(tmp_path, "mark-later", MARK_ON_REDELIVERY), SCENARIO_ID)
    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES


@pytest.mark.parametrize(
    ("ref", "verdict", "fragment"),
    [
        (
            MARK_FIRST_REF,
            CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN,
            "commit 1 of 2 (mark_processed)",
        ),
        (LEFTOVER_CREDIT_REF, CrashVerdict.PATCH_FAILED_STILL_REPRODUCES, "with no crash at all"),
        (NEVER_MARKS_REF, CrashVerdict.PATCH_FAILED_STILL_REPRODUCES, "+$50 duplicate"),
    ],
)
def test_packaged_zoo_variants_get_the_verdict_they_earned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ref: str,
    verdict: CrashVerdict,
    fragment: str,
) -> None:
    """Each packaged zoo tree fooled or nearly fooled an earlier engine; each is one flag away."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY_REF, ref, SCENARIO_ID, mode="local")

    assert result.verdict is verdict, result.summary
    assert fragment in result.summary, result.summary
    assert cli._exit_code(result.verdict) == 1


def test_handler_that_never_credits_is_reported_with_its_no_crash_money(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The kill point is never reached, so there is no crash verdict; the census still says what
    the money did with no crash at all, and the receipt carries it."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "mark-then-atomic", MARK_THEN_ATOMIC)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "without ever committing the credit" in result.summary
    assert "$0.00 instead of $25.00" in result.summary
    assert "never credited" in result.summary
    assert "raised IntegrityError during the replay delivery" in result.summary
    assert "reported, not judged" in result.summary
    sweep = result.sweeps[0]
    assert sweep.role is WorldRole.CANDIDATE
    assert sweep.census.first_delivery_operations == ("mark_processed",)
    first = sweep.census.first_delivery_snapshot
    assert first is not None and (first.subject_total, first.event_marker_count) == (0, 1)
    # The redelivery marks the event a second time and raises, so the census itself is incomplete.
    assert sweep.census.execution_status is ExecutionStatus.REPLAY_ERROR
    assert cli._exit_code(result.verdict) == 2


CREDIT_FLOOD = """def apply_credit(store, event):
    if store.processed(event["event_id"]):
        return
    for _ in range(20):
        store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    store.mark_processed(event["event_id"])
"""


def test_a_flood_of_credits_is_a_failed_patch_not_a_protocol_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red team, round two: twenty credits used to trip a 16-commit protocol cap and become
    EVIDENCE_INCOMPLETE. Money credited twenty times is an observation, so it is judged."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "flood", CREDIT_FLOOD)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN
    assert "credited 21 times" in result.summary
    boundary = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert all(a.execution_status is ExecutionStatus.COMPLETED for a in boundary)
    assert boundary[0].first_worker_operations[:1] == ("credit",)
    assert cli._exit_code(result.verdict) == 1


SIDE_POCKET = """import glob
import sqlite3


def apply_credit(store, event):
    if store.processed(event["event_id"]):
        return
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
    with sqlite3.connect(glob.glob("*.sqlite3")[0], isolation_level=None) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO accounts(account_id, balance_cents) VALUES ('acct_attacker', 1000000)"
        )
        connection.commit()
"""

INVALID_BYTE_THEN_CHILD = """import os
import subprocess
import sys


def apply_credit(store, event):
    os.write(1, b"\\xff")
    os.write(2, b"\\xff")
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(20)"], start_new_session=True)
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""


def test_writes_to_other_accounts_or_events_are_an_integrity_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reviewer finding: attribution watched only this event's four numbers, so a handler could
    fund another account through its own connection and stay PROVEN. Every row outside this event
    must stay exactly as seeded."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "side-pocket", SIDE_POCKET)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert result.integrity_status.value == "INVALID"
    assert "other accounts or events changed" in result.summary


def test_an_invalid_byte_on_stdout_cannot_hide_a_child_that_holds_the_pipes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reviewer finding: the text-mode drain died on one undecodable byte and reported EOF, so a
    detached child holding the worker's pipes went unnoticed. Drains are raw bytes now."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "invalid-byte", INVALID_BYTE_THEN_CHILD)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "inherited the worker's stdout/stderr" in result.summary
    assert result.execution_status is ExecutionStatus.CLEANUP_ERROR


def test_worlds_that_disagree_are_named_not_averaged() -> None:
    """Five worlds report unanimity or nothing; a split is spelled out, never voted on."""
    from nemisis.crashcheck import _unsupported_observation_summary

    result = check(BUGGY_REF, ATOMIC_REF, SCENARIO_ID, mode="local")
    attempts = tuple(a for a in result.attempts if a.role is WorldRole.CANDIDATE)
    split = (
        *attempts[:3],
        *(
            a.model_copy(update={"observation": CrashObservation.DUPLICATE_EFFECT})
            for a in attempts[3:]
        ),
    )

    summary = _unsupported_observation_summary(CrashObservation.NOT_OBSERVED, split)

    assert "worlds disagreed (2 DUPLICATE_EFFECT, 3 EXACTLY_ONCE)" in summary
    assert "unanimity or nothing" in summary


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
    assert (final.subject_total, final.event_effect_count, final.event_marker_count) == (
        5_000,
        2,
        0,
    )
    assert cli._exit_code(result.verdict) == 1


@pytest.mark.parametrize(
    ("name", "source", "detail"),
    [
        ("direct-sql", DIRECT_SQL_EFFECT, "the durable change after mark_processed was not"),
        ("drift", DRIFT_AFTER_LAST_COMMIT, "after the worker's last reported store commit"),
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
    assert "around the trusted store" in result.summary
    assert detail in result.summary
    assert "store.credit_and_mark(account_id, event_id, amount_cents)" in result.summary
    assert "docs/PRODUCT.md#the-store-api" in result.summary
    candidate_attempts = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert len(candidate_attempts) == 5
    assert all(a.execution_status is ExecutionStatus.INTEGRITY_ERROR for a in candidate_attempts)
    assert cli._exit_code(result.verdict) == 2


NO_DURABLE_WRITE = """def apply_credit(store, event):
    if store.processed(event["event_id"]):
        return
"""


def test_raw_sql_judge_handler_is_told_the_one_line_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The textbook atomic fix, written as one raw SQL transaction on the store's own database.
    It is correct, and it is unjudgeable: no store commit means no kill point. The judge who
    writes it in minute one is told, on the first run, the exact store call that earns a verdict,
    in the summary, on the terminal, and in the report card."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY_REF, RAW_SQL_REF, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert cli._exit_code(result.verdict) == 2
    assert "changed the database without a single CreditStore commit" in result.summary
    assert "balance $25.00, 1 credit row(s), 1 marker" in result.summary
    assert "no kill point exists inside that write" in result.summary
    assert "store.credit_and_mark(account_id, event_id, amount_cents)" in result.summary
    assert "docs/PRODUCT.md#the-store-api" in result.summary
    candidate = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert {a.execution_status for a in candidate} == {ExecutionStatus.CHECKPOINT_NOT_REACHED}
    assert all(a.first_worker_operations == () for a in candidate)
    report = (tmp_path / "artifacts" / result.artifacts["report"]).read_text(encoding="utf-8")
    assert "store.credit_and_mark(account_id, event_id, amount_cents)" in report


def test_a_handler_that_writes_nothing_durable_is_told_so_not_blamed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No store commit and no change either: the guard-only handler never credited. That is a
    different sentence from a raw write, and it does not get the raw-SQL remedy."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "no-durable-write", NO_DURABLE_WRITE)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "left the database as seeded" in result.summary
    assert "no durable credit to crash-test" in result.summary
    assert "credit_and_mark" not in result.summary
    assert cli._exit_code(result.verdict) == 2


LYING_STR_ACCOUNT = """class Acct(str):
    def __eq__(self, other):
        return True

    def __hash__(self):
        return 0


def apply_credit(store, event):
    if store.processed(event["event_id"]):
        return
    store.credit_and_mark(Acct("acct_shadow"), event["event_id"], event["amount_cents"])
"""

NULL_MARKER = """def apply_credit(store, event):
    event_id = event["event_id"]
    if store.processed(event_id):
        return
    store.credit(event["account_id"], event_id, event["amount_cents"])
    store.mark_processed(None)
"""


@pytest.mark.parametrize(
    ("name", "source", "status"),
    [
        ("lying-str", LYING_STR_ACCOUNT, ExecutionStatus.CHECKPOINT_NOT_REACHED),
        ("null-marker", NULL_MARKER, ExecutionStatus.REPLAY_ERROR),
    ],
)
def test_store_refuses_look_alike_arguments_instead_of_writing_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, source: str, status: ExecutionStatus
) -> None:
    """Red team, round two: a str subclass with a lying __eq__ used to bind a shadow account into
    the store's own SQL, and mark_processed(None) used to commit a NULL marker row. Both were then
    blamed on 'writes outside the trusted store'. The store now rejects them as ValueErrors."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, name, source)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    candidate_attempts = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert {a.execution_status for a in candidate_attempts} == {status}
    assert result.integrity_status.value == "INCOMPLETE"
    assert "outside the trusted store" not in result.summary


def test_replay_base_role_can_reproduce_but_never_prove_a_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    capsule = _seal_capsule(_audited_contract(CREDIT))

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
    audited = _audited_contract(CREDIT)
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

    result = replay(
        _seal_capsule(_audited_contract(CREDIT)), ATOMIC_REF, role="corrected", mode="live"
    )

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


USER_VERSION_FLAG = """import sqlite3


def apply_credit(store, event):
    connection = sqlite3.connect(store._database, isolation_level=None)
    try:
        if connection.execute("PRAGMA user_version").fetchone()[0] == 1042:
            return
        connection.execute("PRAGMA user_version = 1042")
    finally:
        connection.close()
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

PARENT_DIR_FILE = """import glob
import os


def apply_credit(store, event):
    world = os.path.basename(glob.glob("*.sqlite3")[0])
    guard = os.path.join("..", world + ".inflight")
    if os.path.exists(guard):
        return
    with open(guard, "w", encoding="utf-8") as handle:
        handle.write(event["event_id"])
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

EMPTY_DIR_FLAG = """import os


def apply_credit(store, event):
    try:
        os.mkdir("seen-" + event["event_id"])
    except FileExistsError:
        return
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

HOME_FILE_FLAG = """import os


def apply_credit(store, event):
    guard = os.path.expanduser("~/.seen-" + event["event_id"])
    if os.path.exists(guard):
        return
    open(guard, "w").close()
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

TMPDIR_FILE_FLAG = """import os
import tempfile


def apply_credit(store, event):
    guard = os.path.join(tempfile.gettempdir(), "seen-" + event["event_id"])
    if os.path.exists(guard):
        return
    open(guard, "w").close()
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

REPOINTED_LEDGER = """import sqlite3


def apply_credit(store, event):
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
    connection = sqlite3.connect(store._database, timeout=5, isolation_level=None)
    try:
        connection.execute(
            "UPDATE credit_ledger SET account_id = 'acct_9000' WHERE event_id = ?",
            (event["event_id"],),
        )
    finally:
        connection.close()
"""

SCHEMA_SWAP = """import sqlite3


def apply_credit(store, event):
    connection = sqlite3.connect(store._database, timeout=5, isolation_level=None)
    try:
        archived = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='accounts_archived'"
        ).fetchone()
        if archived is None:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("ALTER TABLE accounts RENAME TO accounts_archived")
            connection.execute(
                "CREATE TABLE accounts("
                "account_id TEXT PRIMARY KEY, balance_cents INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT INTO accounts SELECT account_id, balance_cents FROM accounts_archived"
            )
            connection.commit()
    finally:
        connection.close()
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

OTHER_ACCOUNT_NO_COMMIT = """import sqlite3


def apply_credit(store, event):
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute(
            "INSERT INTO accounts(account_id, balance_cents) VALUES ('acct_sweep', 2500)"
        )
        connection.commit()
"""


@pytest.mark.parametrize(
    ("name", "source", "status", "fragment"),
    [
        (
            "user-version",
            USER_VERSION_FLAG,
            ExecutionStatus.INTEGRITY_ERROR,
            "the database header changed (PRAGMA user_version",
        ),
        (
            "parent-dir-file",
            PARENT_DIR_FILE,
            ExecutionStatus.UNSUPPORTED,
            "wrote durable entries outside the store",
        ),
        ("empty-dir", EMPTY_DIR_FLAG, ExecutionStatus.UNSUPPORTED, "seen-evt_1042/"),
        ("home-file", HOME_FILE_FLAG, ExecutionStatus.UNSUPPORTED, "home/.seen-evt_1042"),
        ("tmpdir-file", TMPDIR_FILE_FLAG, ExecutionStatus.UNSUPPORTED, "tmp/seen-evt_1042"),
        (
            "repointed-ledger",
            REPOINTED_LEDGER,
            ExecutionStatus.INTEGRITY_ERROR,
            "after the worker's last reported store commit",
        ),
        ("schema-swap", SCHEMA_SWAP, ExecutionStatus.INTEGRITY_ERROR, "the schema changed"),
    ],
)
def test_dedup_state_hidden_from_the_probes_forfeits_the_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    source: str,
    status: ExecutionStatus,
    fragment: str,
) -> None:
    """Hostile review of 2026-09-06: each of these earned FIX_PROVEN_FOR_THIS_CAPSULE while a
    crash between its own durable write and the store's commit lost the credit (or, for the
    re-pointed ledger row and the schema swap, moved it). Attribution now covers the whole
    database (schema, header pragmas, every row of every table) and the whole world the worker
    runs in (its cwd, the two directories above it, HOME, and TMPDIR)."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, name, source)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE, result.summary
    assert fragment in result.summary, result.summary
    worlds = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert {a.execution_status for a in worlds} == {status}, result.summary
    assert cli._exit_code(result.verdict) == 2


def test_shadow_table_is_a_packaged_zoo_tree_pinned_to_no_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The best handler the hostile review found ships as fixture:sqlite-credit-v1/shadow-table."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY_REF, SHADOW_TABLE_REF, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert result.integrity_status.value == "INVALID"
    assert "the schema changed (a table, index, or trigger this scenario did not seed)" in (
        result.summary
    )
    assert "store.credit_and_mark(account_id, event_id, amount_cents)" in result.summary
    assert cli._exit_code(result.verdict) == 2


def test_a_raw_write_to_another_account_with_no_commit_is_named_not_called_seeded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hostile review: this used to be told it 'left the database as seeded' with the money
    'moved' and every number zero. The whole-database comparison names the row that changed."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "other-account", OTHER_ACCOUNT_NO_COMMIT)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "left the database as seeded" not in result.summary
    assert "rows that belong to other accounts or events changed" in result.summary
    assert "in accounts" in result.summary
    assert "store.credit_and_mark(account_id, event_id, amount_cents)" in result.summary


SPLIT_SCHEDULE = """import os


def apply_credit(store, event):
    # A counter by absolute path outside every world: the first five deliveries mark first,
    # later ones are atomic. The five kill worlds see one schedule, the census another; the
    # sweep would kill only at the census's commits.
    counter = "/var/tmp/nemisis-split-__TOKEN__"
    try:
        with open(counter, "r+", encoding="utf-8") as handle:
            seen = int(handle.read() or "0") + 1
            handle.seek(0)
            handle.write(str(seen))
    except FileNotFoundError:
        seen = 1
        with open(counter, "w", encoding="utf-8") as handle:
            handle.write("1")
    if store.processed(event["event_id"]):
        return
    if seen <= 5:
        store.mark_processed(event["event_id"])
        store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    else:
        store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""


def test_a_schedule_that_differs_between_worlds_is_named_not_swept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hostile review: a handler keeping state by absolute path (outside every world, the
    documented boundary) can show the five kill worlds one commit schedule and the census
    another; the sweep derived its kill points from the census alone and blessed the losing
    patch. A kill world's commits must now be a prefix of the census's."""
    import uuid

    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    token = uuid.uuid4().hex
    counter = Path("/var/tmp") / f"nemisis-split-{token}"
    candidate = _tree(tmp_path, "split-schedule", SPLIT_SCHEDULE.replace("__TOKEN__", token))
    try:
        result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")
    finally:
        counter.unlink(missing_ok=True)

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE, result.summary
    assert "commit schedule differs between worlds" in result.summary, result.summary


def test_an_effect_without_its_marker_is_described_not_left_as_x_instead_of_x() -> None:
    """Hostile review: the fallback sentence read '$25.00 instead of $25.00 ... matches neither'.
    A landed effect with no marker is the shape a retry will double; both scenarios name it."""
    from nemisis.crash_models import StateSnapshot
    from nemisis.scenarios.sqlite_credit_v1 import SCENARIO as CREDIT_SCENARIO
    from nemisis.scenarios.sqlite_inventory_v1 import SCENARIO as INVENTORY

    credited = StateSnapshot.with_digest(
        subject_total=2500, event_effect_count=1, event_effect_total=2500, event_marker_count=0
    )
    text = CREDIT_SCENARIO.describe_final(
        credited, {"account_id": "acct_7", "amount_cents": 2500, "event_id": "evt_1042"}
    )
    assert "never marked processed, so the next retry credits it again" in text
    assert "instead of $25.00" in text
    reserved = StateSnapshot.with_digest(
        subject_total=8, event_effect_count=1, event_effect_total=-2, event_marker_count=0
    )
    text = INVENTORY.describe_final(
        reserved, {"event_id": "order-1", "quantity": 2, "sku": "widget"}
    )
    assert "reserved but never marked, so the next retry reserves it again" in text


JOURNAL_MODE_FLAG = """import sqlite3


def apply_credit(store, event):
    connection = sqlite3.connect(store._database, timeout=5)
    try:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        if str(mode).lower() == "delete":
            return
        connection.execute("PRAGMA journal_mode=DELETE")
    finally:
        connection.close()
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

ROWID_FLAG = """import sqlite3


def apply_credit(store, event):
    connection = sqlite3.connect(store._database, timeout=5, isolation_level=None)
    try:
        row = connection.execute(
            "SELECT rowid FROM accounts WHERE account_id = ?", (event["account_id"],)
        ).fetchone()
        if row is not None and row[0] == 424242:
            return
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE accounts SET rowid = 424242 WHERE account_id = ?", (event["account_id"],)
        )
        connection.commit()
    finally:
        connection.close()
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

FREELIST_FLAG = """import sqlite3


def apply_credit(store, event):
    connection = sqlite3.connect(store._database, timeout=5, isolation_level=None)
    try:
        if connection.execute("PRAGMA freelist_count").fetchone()[0] > 0:
            return
        connection.execute("CREATE TABLE scratch(a TEXT)")
        connection.execute("INSERT INTO scratch(a) VALUES (?)", ("x" * 4000,))
        connection.execute("DROP TABLE scratch")
    finally:
        connection.close()
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

SCHEMA_VERSION_FLAG = """import sqlite3


def apply_credit(store, event):
    connection = sqlite3.connect(store._database, timeout=5, isolation_level=None)
    try:
        if connection.execute("PRAGMA schema_version").fetchone()[0] >= 1000:
            return
        connection.execute("PRAGMA writable_schema=ON")
        connection.execute("PRAGMA schema_version=1000")
        connection.execute("PRAGMA writable_schema=OFF")
    finally:
        connection.close()
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

DELETED_ON_EXIT_FLAG = """import os


def apply_credit(store, event):
    guard = "inflight-" + event["event_id"]
    if os.path.exists(guard):
        os.remove(guard)
        return
    with open(guard, "w", encoding="utf-8") as handle:
        handle.write(event["event_id"])
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
    os.remove(guard)
"""

PYCACHE_FLAG = """import os


def apply_credit(store, event):
    world = os.path.basename(os.path.dirname(os.path.dirname(os.getcwd())))
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "__pycache__")
    os.makedirs(cache, exist_ok=True)
    guard = os.path.join(cache, world + ".inflight")
    if os.path.exists(guard):
        return
    with open(guard, "w", encoding="utf-8") as handle:
        handle.write(event["event_id"])
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

TREE_DIR_FLAG = """import os


def apply_credit(store, event):
    world = os.path.basename(os.path.dirname(os.path.dirname(os.getcwd())))
    marker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lock." + world)
    if os.path.isdir(marker):
        return
    os.mkdir(marker)
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

CHMOD_FLAG = """import os
import stat


def apply_credit(store, event):
    path = str(store._database)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & stat.S_IXUSR:
        return
    os.chmod(path, mode | stat.S_IXUSR)
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

BLOB_AMOUNT = """import sqlite3


def apply_credit(store, event):
    if store.processed(event["event_id"]):
        return
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    connection = sqlite3.connect(store._database, timeout=5, isolation_level=None)
    try:
        connection.execute(
            "UPDATE credit_ledger SET amount_cents = x'ff' WHERE event_id = ?",
            (event["event_id"],),
        )
    finally:
        connection.close()
    store.mark_processed(event["event_id"])
"""

WORLD_UP_FLAG = """import os


def apply_credit(store, event):
    world = os.path.basename(os.path.dirname(os.path.dirname(os.getcwd())))
    guard = os.path.join("..", "..", "..", world + ".inflight")
    if os.path.exists(guard):
        return
    with open(guard, "w", encoding="utf-8") as handle:
        handle.write(event["event_id"])
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""


@pytest.mark.parametrize(
    ("name", "source", "fragment"),
    [
        # The seed now stays in WAL, so flipping the mode either shows in the header or breaks
        # the store's own next connection; both are refusals, neither is a verdict.
        ("journal-mode", JOURNAL_MODE_FLAG, "did not complete"),
        ("rowid", ROWID_FLAG, "rows that belong to other accounts or events changed"),
        ("freelist", FREELIST_FLAG, "the database header changed"),
        ("schema-version", SCHEMA_VERSION_FLAG, "the database header changed"),
        ("deleted-on-exit", DELETED_ON_EXIT_FLAG, "wrote durable entries outside the store"),
        ("pycache", PYCACHE_FLAG, "source tree changed"),
        ("tree-dir", TREE_DIR_FLAG, "source tree changed"),
        ("chmod", CHMOD_FLAG, "permission bits or extended attributes"),
        ("blob", BLOB_AMOUNT, "was not"),
    ],
)
def test_side_channels_from_the_second_hostile_review_forfeit_the_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, source: str, fragment: str
) -> None:
    """Hostile review of the whole-database fix: a flag in the journal-mode header bits (the
    store's own first connection used to flip them), a rowid, the free-page count, the schema
    cookie, a file deleted before exit, a bytecode-cache file or an empty directory in the bound
    tree, and the database's permission bits each earned FIX_PROVEN. Each is a write no store
    commit made, and each now forfeits the verdict with a sentence that names it."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, name, source)

    result = check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE, result.summary
    assert fragment in result.summary, result.summary
    assert cli._exit_code(result.verdict) == 2


def test_a_flag_written_into_the_scratch_tree_stops_the_run_without_a_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hostile review: ``../../..`` from the worker's cwd is CrashCheck's own scratch tree, shared
    by every sibling world. Anything a handler leaves there stops the run, named."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    candidate = _tree(tmp_path, "world-up", WORLD_UP_FLAG)

    with pytest.raises(CrashCheckError, match="wrote outside its world into CrashCheck's scratch"):
        check(BUGGY_REF, candidate, SCENARIO_ID, mode="local")
