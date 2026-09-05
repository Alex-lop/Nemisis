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
    assert "wrote durable files outside the store" in result.summary
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
    from nemisis.crash_models import CreditSnapshot, classify_delivery

    once = CreditSnapshot.with_digest(
        account_balance_cents=2500,
        event_ledger_count=1,
        event_ledger_total_cents=2500,
        event_marker_count=1,
    )
    unmarked = CreditSnapshot.with_digest(
        account_balance_cents=2500,
        event_ledger_count=1,
        event_ledger_total_cents=2500,
        event_marker_count=0,
    )
    assert classify_delivery(once, once, 2500) is CrashObservation.EXACTLY_ONCE
    assert classify_delivery(unmarked, once, 2500) is CrashObservation.INVARIANT_FAILED
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
    assert first is not None and (first.account_balance_cents, first.event_marker_count) == (0, 1)
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
    assert (final.account_balance_cents, final.event_ledger_count, final.event_marker_count) == (
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
    candidate_attempts = [a for a in result.attempts if a.role is WorldRole.CANDIDATE]
    assert len(candidate_attempts) == 5
    assert all(a.execution_status is ExecutionStatus.INTEGRITY_ERROR for a in candidate_attempts)
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
