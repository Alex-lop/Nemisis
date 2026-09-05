from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from nemisis.crash_models import (
    CrashCheckResult,
    CrashObservation,
    CrashVerdict,
    CreditSnapshot,
    ExecutionStatus,
    FaultBoundary,
    IntegrityStatus,
    ReproCapsule,
    WorldRole,
)
from nemisis.models import TruthLabel
from nemisis.report import write_crash_report


def _render_report(
    tmp_path: Path,
    *,
    complete: bool,
    fixed: bool = False,
    minimization_irreducible: bool | None = None,
) -> str:
    checkpoint = cast(
        CreditSnapshot,
        SimpleNamespace(
            account_balance_cents=1234,
            event_ledger_count=1,
            event_marker_count=0,
        ),
    )
    final = cast(
        CreditSnapshot,
        SimpleNamespace(
            account_balance_cents=1234 if fixed else 2468,
            event_ledger_count=1 if fixed else 2,
            event_marker_count=1,
        ),
    )
    spawns = (
        SimpleNamespace(
            phase="first",
            spawn_index=1,
            pid=101,
            process_group_id=201,
            worker_nonce="first-worker",
            ipc_session_id="first-session",
            exit_code=-15,
        ),
        SimpleNamespace(
            phase="replay",
            spawn_index=2,
            pid=102,
            process_group_id=202,
            worker_nonce="replay-worker<&",
            ipc_session_id="replay-session<&",
            exit_code=0,
        ),
    )
    attempt = SimpleNamespace(
        receipt_id="attempt-<unsafe>",
        role=WorldRole.CANDIDATE,
        execution_status=(ExecutionStatus.COMPLETED if complete else ExecutionStatus.UNSUPPORTED),
        observation=(
            CrashObservation.EXACTLY_ONCE
            if fixed
            else (CrashObservation.DUPLICATE_EFFECT if complete else CrashObservation.NOT_OBSERVED)
        ),
        checkpoint_snapshot=checkpoint if complete else None,
        final_snapshot=final if complete else None,
        checkpoint_reached=complete,
        spawns=spawns if complete else (),
        kill_signal=15 if complete else None,
        replay_acknowledged=complete,
        event_digest="event-digest<&",
        failure_detail=None if complete else "blocked by <script>alert(1)</script>",
    )
    transport = TruthLabel.LOCAL if complete else TruthLabel.LIVE
    bindings = (
        SimpleNamespace(
            source_ref="candidate<&",
            resolved_source_identity="resolved<one>",
            tree_digest="tree-digest<&",
        ),
        SimpleNamespace(
            source_ref="corrected-ref",
            resolved_source_identity="resolved-two",
            tree_digest="tree-digest-two",
        ),
    )
    result = cast(
        CrashCheckResult,
        SimpleNamespace(
            attempts=(attempt,),
            bindings=bindings,
            transport=transport,
            execution_status=attempt.execution_status,
            integrity_status=(IntegrityStatus.VALID if complete else IntegrityStatus.INCOMPLETE),
            verdict=(
                CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
                if fixed
                else (
                    CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
                    if complete
                    else CrashVerdict.EVIDENCE_INCOMPLETE
                )
            ),
            summary="summary <b>must be escaped</b>",
            engine_code_digest="e" * 64,
            engine_source_commit="a" * 40,
            hypothesis_receipts=(
                SimpleNamespace(
                    canonical_rank=1,
                    hypothesis_id="effect-commit-v1",
                    fault_boundary=FaultBoundary.EFFECT_COMMIT,
                    trusted_operation_count=1,
                    reproduced=True,
                    selected=True,
                ),
                SimpleNamespace(
                    canonical_rank=2,
                    hypothesis_id="marker-commit-v1",
                    fault_boundary=FaultBoundary.MARKER_COMMIT,
                    trusted_operation_count=2,
                    reproduced=False,
                    selected=False,
                ),
            )
            if complete
            else (),
            minimization_receipts=(
                SimpleNamespace(
                    removed_fault=FaultBoundary.EFFECT_COMMIT,
                    confirmations=(
                        SimpleNamespace(
                            observation=(
                                CrashObservation.EXACTLY_ONCE
                                if minimization_irreducible is not False
                                else CrashObservation.NOT_OBSERVED
                            )
                        ),
                        SimpleNamespace(
                            observation=(
                                CrashObservation.EXACTLY_ONCE
                                if minimization_irreducible is not False
                                else CrashObservation.NOT_OBSERVED
                            )
                        ),
                    ),
                    sole_fault_action_necessary_for_fixture=(minimization_irreducible is not False),
                    trace_digest="m" * 64,
                ),
            )
            if complete
            else (),
            model_dump=lambda **_: {"unsafe": "</pre><script>alert(2)</script>"},
        ),
    )
    capsule = cast(
        ReproCapsule,
        SimpleNamespace(
            event_id="evt_report",
            account_id="acct_report",
            amount_cents=1234,
            truth_label=TruthLabel.FIXTURE if complete else TruthLabel.LOCAL,
            digest="capsule-digest<&",
            model_dump=lambda **_: {"event_id": "evt_report"},
        ),
    )
    path = tmp_path / "report.html"

    write_crash_report(result, capsule, path)

    return path.read_text(encoding="utf-8")


def test_crash_report_uses_receipt_and_capsule_values_and_escapes_html(tmp_path: Path) -> None:
    report = _render_report(tmp_path, complete=True)

    assert "LOCAL EXECUTION · AUDITED FIXTURE CAPSULE" in report
    assert '<main id="main" class="verdict-fail">' in report
    assert "Patch still duplicates the effect" in report
    assert "Expected single effect</span>\n<strong>$12.34</strong>" in report
    assert "Observed final balance</span><strong>$24.68</strong>" in report
    assert "<strong>Checkpoint reached.</strong> $12.34 / ledger 1 / marker 0" in report
    assert "<strong>Kill recorded.</strong> Signal 15; first worker PID 101" in report
    assert "process group 201, exit -15" in report
    assert "<strong>Fresh replay worker.</strong> Spawn 2; PID 102, process group 202" in report
    assert "replay-worker&lt;&amp;" in report
    assert "replay-session&lt;&amp;" in report
    assert "<strong>Replay acknowledged.</strong> Event <code>evt_report</code>" in report
    assert "<strong>Final state observed.</strong> $24.68 / ledger 2 / marker 1" in report
    assert f"<code>{'a' * 40}</code>" in report
    assert f"<code>{'e' * 64}</code>" in report
    assert "2-hypothesis candidate-blind hunt" in report
    assert "Selected outcome: REPRODUCED · 1 of 2 selected" in report
    assert "effect-commit-v1" in report
    assert "marker-commit-v1" in report
    assert "REPRODUCED" in report
    assert "NOT REPRODUCED" in report
    assert "No-crash control" in report
    assert "Delivered the event twice with no kill in 2 fresh base worlds" in report
    assert "the duplicate needs the kill" in report
    assert "minimizer" not in report
    assert "event-digest&lt;&amp;" in report
    assert "attempt-&lt;unsafe&gt;" in report
    assert "capsule-digest&lt;&amp;" in report
    assert "summary &lt;b&gt;must be escaped&lt;/b&gt;" in report
    assert "candidate&lt;&amp;" in report
    assert "resolved&lt;one&gt;" in report
    assert "tree-digest&lt;&amp;" in report
    assert "corrected-ref" in report
    assert "resolved-two" in report
    assert "tree-digest-two" in report
    assert "<script>" not in report
    assert "$25" not in report
    assert "evt_1042" not in report
    assert "Five fresh worlds" not in report
    assert "byte-identical" not in report
    assert report.index("Expected single effect") < report.index("Independent result axes")


def test_fixed_report_prominently_shows_exact_observed_effect_in_green(tmp_path: Path) -> None:
    report = _render_report(tmp_path, complete=True, fixed=True)

    assert '<main id="main" class="verdict-pass">' in report
    assert "Fix proven for this capsule only" in report
    assert "Expected single effect</span>\n<strong>$12.34</strong>" in report
    assert "Observed final balance</span><strong>$12.34</strong>" in report
    assert "EXACTLY_ONCE" in report


def test_incomplete_report_makes_no_success_claim_and_uses_semantic_html(tmp_path: Path) -> None:
    report = _render_report(tmp_path, complete=False)

    assert "LIVE MODE REQUESTED · ACCEPTED LOCAL CAPSULE" in report
    assert '<main id="main" class="verdict-warn">' in report
    assert "Observed final balance</span><strong>Not recorded</strong>" in report
    assert "<strong>Checkpoint not recorded.</strong>" in report
    assert "<strong>No kill signal recorded.</strong>" in report
    assert "<strong>No replay-worker spawn receipt recorded.</strong>" in report
    assert "<strong>Replay not acknowledged.</strong>" in report
    assert "<strong>Final state not recorded.</strong>" in report
    assert "blocked by &lt;script&gt;alert(1)&lt;/script&gt;" in report
    assert "real process-group SIGKILL" not in report
    assert "hypothesis hunt and minimization" not in report
    assert "No-crash control" not in report
    assert "Selected outcome" not in report
    assert "<head>" in report
    assert '<main id="main" class="verdict-warn">' in report
    assert '<dl class="axes" aria-label="Independent result axes">' in report
    assert '<ol class="timeline">' in report
    assert '<th scope="row">' in report
    assert '<th scope="col">' in report


def test_crash_report_makes_no_minimization_claim_for_incomplete_evidence(
    tmp_path: Path,
) -> None:
    report = _render_report(tmp_path, complete=True, minimization_irreducible=False)

    assert "No-crash control" in report
    assert "did not complete, so the duplicate is not attributed" in report
    assert "needs the kill" not in report
    assert "<caption>1 receipt(s) across 2 source-tree binding(s).</caption>" in report
