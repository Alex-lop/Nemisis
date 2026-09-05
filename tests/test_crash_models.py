from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import pytest
from pydantic import ValidationError

from nemisis.crash_models import (
    REQUIRED_CONFIRMATIONS,
    AnchorBinding,
    AttemptReceipt,
    CommitSweepReceipt,
    CrashCheckResult,
    CrashObservation,
    CrashVerdict,
    CreditSnapshot,
    ExecutionStatus,
    FaultBoundary,
    HypothesisReceipt,
    IntegrityStatus,
    MinimizationReceipt,
    NoFaultReplayReceipt,
    ReproCapsule,
    TimelineEntry,
    TimelineState,
    WorkerSpawnReceipt,
    WorldRole,
)
from nemisis.hashing import canonical_json, sha256_json
from nemisis.models import TruthLabel

NOW = datetime(2026, 8, 30, tzinfo=UTC)
HASHES = tuple(f"{index:x}" * 64 for index in range(10))


def _snapshot(*, effects: int = 1, marker: int = 1) -> CreditSnapshot:
    return CreditSnapshot.with_digest(
        account_balance_cents=2_500 * effects,
        event_ledger_count=effects,
        event_ledger_total_cents=2_500 * effects,
        event_marker_count=marker,
    )


def _capsule() -> ReproCapsule:
    event = {"account_id": "acct-7", "amount_cents": 2_500, "event_id": "evt-1042"}
    return ReproCapsule.with_digest(
        contract_digest=HASHES[0],
        originating_base_tree_digest=HASHES[4],
        engine_code_digest=HASHES[9],
        scenario_id="sqlite-credit-v1",
        scenario_version="v1",
        event_id=event["event_id"],
        account_id=event["account_id"],
        amount_cents=event["amount_cents"],
        event_digest=sha256_json(event),
        fault_intent_id="after-credit-before-marker",
        fault_boundary=FaultBoundary.EFFECT_COMMIT,
        probe_id="credit-state-v1",
        predicate_ids=("single-credit", "single-marker"),
        runner_id="sqlite-credit-runner-v1",
        runner_version="v1",
        environment_digest=HASHES[2],
        initial_database_digest=HASHES[3],
        minimization_trace=("first-durable-credit",),
        truth_label=TruthLabel.FIXTURE,
    )


def _capsule_for_boundary(
    boundary: FaultBoundary, capsule: ReproCapsule | None = None
) -> ReproCapsule:
    values = (capsule or _capsule()).model_dump(mode="python", exclude={"digest"})
    values["fault_boundary"] = boundary
    return ReproCapsule.with_digest(**values)


def _binding(
    capsule: ReproCapsule,
    *,
    source_ref: str = "fixture:sqlite-credit-v1/buggy",
    tree_digest: str = HASHES[4],
) -> AnchorBinding:
    return AnchorBinding.with_digest(
        contract_digest=capsule.contract_digest,
        scenario_id=capsule.scenario_id,
        source_ref=source_ref,
        resolved_source_identity=source_ref,
        tree_digest=tree_digest,
        handler_path="app/credits.py",
        handler_symbol="apply_credit",
        adapter_id="sqlite-credit-v1",
        fault_intent_id=capsule.fault_intent_id,
    )


def _worker(
    index: int, phase: Literal["first", "replay"], *, nonce: str, session: str
) -> WorkerSpawnReceipt:
    return WorkerSpawnReceipt(
        spawn_index=index,
        phase=phase,
        pid=1_000 + index,
        process_group_id=1_000 + index,
        worker_nonce=nonce,
        ipc_session_id=session,
        event_digest=_capsule().event_digest,
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=index),
        exit_code=-9 if phase == "first" else 0,
        stdout_excerpt="",
        stderr_excerpt="",
        stdout_digest=HASHES[5],
        stderr_digest=HASHES[6],
    )


def _attempt_values(
    capsule: ReproCapsule,
    binding: AnchorBinding,
    *,
    role: WorldRole = WorldRole.CANDIDATE,
    transport: TruthLabel = TruthLabel.LOCAL,
    observation: CrashObservation = CrashObservation.EXACTLY_ONCE,
    index: int = 1,
) -> dict[str, object]:
    duplicate = observation is CrashObservation.DUPLICATE_EFFECT
    checkpoint = _snapshot(marker=0) if duplicate else _snapshot()
    final = {
        CrashObservation.DUPLICATE_EFFECT: _snapshot(effects=2),
        CrashObservation.INVARIANT_FAILED: _snapshot(effects=3),
    }.get(observation, _snapshot())
    return {
        "receipt_id": f"{role.value}-attempt-{index}",
        "role": role,
        "transport": transport,
        "execution_status": ExecutionStatus.COMPLETED,
        "integrity_status": IntegrityStatus.VALID,
        "observation": observation,
        "capsule_digest": capsule.digest,
        "contract_digest": capsule.contract_digest,
        "binding_digest": binding.digest,
        "tree_digest": binding.tree_digest,
        "post_execution_tree_digest": binding.tree_digest,
        "environment_digest": capsule.environment_digest,
        "event_digest": capsule.event_digest,
        "amount_cents": capsule.amount_cents,
        "initial_database_digest": capsule.initial_database_digest,
        "initial_database_file_digest": HASHES[7],
        "database_id": f"database-{role.value}-{index}",
        "execution_nonce": f"execution-{role.value}-{index}",
        "started_at": NOW,
        "ended_at": NOW + timedelta(seconds=3),
        "timeline": (
            TimelineEntry(state=TimelineState.PREFLIGHT, timestamp=NOW),
            TimelineEntry(state=TimelineState.COMPLETE, timestamp=NOW + timedelta(seconds=3)),
        ),
        "spawns": (
            _worker(
                1,
                "first",
                nonce=f"worker-{role.value}-{index}-1",
                session=f"session-{role.value}-{index}-1",
            ),
            _worker(
                2,
                "replay",
                nonce=f"worker-{role.value}-{index}-2",
                session=f"session-{role.value}-{index}-2",
            ),
        ),
        "pre_crash_snapshot": _snapshot(effects=0, marker=0),
        "checkpoint_snapshot": checkpoint,
        "post_kill_snapshot": checkpoint,
        "final_snapshot": final,
        "checkpoint_reached": True,
        "kill_signal": 9,
        "replay_acknowledged": True,
    }


def _confirmations(
    capsule: ReproCapsule,
    binding: AnchorBinding,
    first: AttemptReceipt,
) -> tuple[AttemptReceipt, ...]:
    if first.execution_status is not ExecutionStatus.COMPLETED:
        return (first,)
    return (
        first,
        *(
            AttemptReceipt.with_digest(
                **_attempt_values(
                    capsule,
                    binding,
                    role=first.role,
                    transport=first.transport,
                    observation=first.observation,
                    index=index,
                )
            )
            for index in range(2, REQUIRED_CONFIRMATIONS + 1)
        ),
    )


def _hypothesis_receipts(capsule: ReproCapsule) -> tuple[HypothesisReceipt, ...]:
    marker_capsule = _capsule_for_boundary(FaultBoundary.MARKER_COMMIT, capsule)
    values = (
        (
            1,
            "effect-commit-v1",
            capsule,
            CrashObservation.DUPLICATE_EFFECT,
            True,
        ),
        (2, "marker-commit-v1", marker_capsule, CrashObservation.EXACTLY_ONCE, False),
    )
    return tuple(
        HypothesisReceipt.with_digest(
            canonical_rank=rank,
            hypothesis_id=hypothesis_id,
            contract_digest=provisional.contract_digest,
            originating_base_tree_digest=provisional.originating_base_tree_digest,
            fault_boundary=provisional.fault_boundary,
            trusted_operation_count=rank,
            reproduced=reproduced,
            selected=rank == 1,
            provisional_capsule_digest=provisional.digest,
            attempt=AttemptReceipt.with_digest(
                **_attempt_values(
                    provisional,
                    _binding(
                        provisional,
                        tree_digest=provisional.originating_base_tree_digest,
                    ),
                    role=WorldRole.BASE,
                    observation=observation,
                    index=rank + 100,
                )
            ),
        )
        for rank, hypothesis_id, provisional, observation, reproduced in values
    )


def _hypothesis_values(receipt: HypothesisReceipt) -> dict[str, object]:
    return {
        name: getattr(receipt, name) for name in HypothesisReceipt.model_fields if name != "digest"
    }


def _no_fault_receipt(
    capsule: ReproCapsule,
    binding: AnchorBinding,
    index: int,
    *,
    role: WorldRole = WorldRole.BASE,
    operations: tuple[str, ...] = ("credit", "mark_processed"),
) -> NoFaultReplayReceipt:
    workers = (
        _worker(
            1,
            "first",
            nonce=f"min-worker-{index}-1",
            session=f"min-session-{index}-1",
        ).model_copy(update={"exit_code": 0}),
        _worker(
            2,
            "replay",
            nonce=f"min-worker-{index}-2",
            session=f"min-session-{index}-2",
        ).model_copy(update={"exit_code": 0}),
    )
    return NoFaultReplayReceipt.with_digest(
        receipt_id=f"minimization-{index}",
        role=role,
        execution_status=ExecutionStatus.COMPLETED,
        integrity_status=IntegrityStatus.VALID,
        observation=CrashObservation.EXACTLY_ONCE,
        parent_capsule_digest=capsule.digest,
        contract_digest=capsule.contract_digest,
        binding_digest=binding.digest,
        tree_digest=binding.tree_digest,
        post_execution_tree_digest=binding.tree_digest,
        environment_digest=capsule.environment_digest,
        event_digest=capsule.event_digest,
        amount_cents=capsule.amount_cents,
        initial_database_digest=capsule.initial_database_digest,
        initial_database_file_digest=HASHES[7],
        database_id=f"min-database-{index}",
        execution_nonce=f"min-execution-{index}",
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=3),
        spawns=workers,
        first_delivery_operations=operations,
        first_delivery_commit_count=len(operations),
        initial_snapshot=_snapshot(effects=0, marker=0),
        first_delivery_snapshot=_snapshot(),
        final_snapshot=_snapshot(),
    )


def _sweep(
    capsule: ReproCapsule,
    binding: AnchorBinding,
    *,
    role: WorldRole = WorldRole.CANDIDATE,
    observation: CrashObservation = CrashObservation.EXACTLY_ONCE,
) -> CommitSweepReceipt:
    """One-commit census plus one kill point; identities live in the 900 range."""
    census = _no_fault_receipt(
        capsule,
        binding,
        900 + (1 if role is WorldRole.CANDIDATE else 2),
        role=role,
        operations=("credit_and_mark",),
    )
    values = _attempt_values(capsule, binding, role=role, observation=observation, index=950)
    values["kill_after_commit"] = 1
    if observation is CrashObservation.INVARIANT_FAILED:
        values["final_snapshot"] = _snapshot(effects=0, marker=1)
        values["checkpoint_snapshot"] = _snapshot(effects=0, marker=1)
        values["post_kill_snapshot"] = _snapshot(effects=0, marker=1)
    attempt = AttemptReceipt.with_digest(**values)
    return CommitSweepReceipt.with_digest(
        role=role,
        capsule_digest=capsule.digest,
        binding_digest=binding.digest,
        census=census,
        attempts=(attempt,),
        observation=observation,
    )


def _minimization_receipts(
    capsule: ReproCapsule, binding: AnchorBinding
) -> tuple[MinimizationReceipt]:
    confirmations = (
        _no_fault_receipt(capsule, binding, 1),
        _no_fault_receipt(capsule, binding, 2),
    )
    stable = {
        "candidate_schedule": (),
        "confirmation_count": 2,
        "contract_digest": capsule.contract_digest,
        "sole_fault_action_necessary_for_fixture": True,
        "originating_base_tree_digest": binding.tree_digest,
        "parent_capsule_digest": capsule.digest,
        "parent_schedule": (FaultBoundary.EFFECT_COMMIT,),
        "removed_fault": FaultBoundary.EFFECT_COMMIT,
        "empty_schedule_reproduced_duplicate": False,
        "deletion_accepted": False,
    }
    return (
        MinimizationReceipt.with_digest(
            parent_capsule_digest=capsule.digest,
            contract_digest=capsule.contract_digest,
            originating_base_tree_digest=binding.tree_digest,
            parent_schedule=(FaultBoundary.EFFECT_COMMIT,),
            candidate_schedule=(),
            removed_fault=FaultBoundary.EFFECT_COMMIT,
            confirmations=confirmations,
            empty_schedule_reproduced_duplicate=False,
            deletion_accepted=False,
            sole_fault_action_necessary_for_fixture=True,
            trace_digest=sha256_json(stable),
        ),
    )


def _attempt_receipt_values(receipt: AttemptReceipt) -> dict[str, object]:
    return {
        name: getattr(receipt, name) for name in AttemptReceipt.model_fields if name != "digest"
    }


def _result_values(
    capsule: ReproCapsule, binding: AnchorBinding, attempt: AttemptReceipt
) -> dict[str, object]:
    return {
        "run_id": "local-run-1",
        "transport": TruthLabel.LOCAL,
        "execution_status": ExecutionStatus.COMPLETED,
        "integrity_status": IntegrityStatus.VALID,
        "verdict": CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE,
        "capsule_digest": capsule.digest,
        "engine_code_digest": capsule.engine_code_digest,
        "hypothesis_receipts": (),
        "bindings": (binding,),
        "attempts": _confirmations(capsule, binding, attempt),
        "sweeps": (
            (_sweep(capsule, binding, role=attempt.role),)
            if attempt.role is not WorldRole.BASE
            and attempt.observation is CrashObservation.EXACTLY_ONCE
            and attempt.transport is TruthLabel.LOCAL
            else ()
        ),
        "started_at": NOW,
        "ended_at": NOW + timedelta(seconds=4),
        "summary": "exact patch defeated the capsule",
        "engine_source_commit": "a" * 40,
    }


def _full_result_values(capsule: ReproCapsule) -> dict[str, object]:
    base = _binding(capsule, source_ref="fixture:base", tree_digest=HASHES[4])
    candidate = _binding(capsule, source_ref="fixture:candidate", tree_digest=HASHES[5])
    base_attempt = AttemptReceipt.with_digest(
        **_attempt_values(
            capsule,
            base,
            role=WorldRole.BASE,
            observation=CrashObservation.DUPLICATE_EFFECT,
        )
    )
    candidate_attempt = AttemptReceipt.with_digest(
        **_attempt_values(capsule, candidate, role=WorldRole.CANDIDATE)
    )
    values = _result_values(capsule, candidate, candidate_attempt)
    values.update(
        bindings=(base, candidate),
        attempts=(
            *_confirmations(capsule, base, base_attempt),
            *_confirmations(capsule, candidate, candidate_attempt),
        ),
        hypothesis_receipts=_hypothesis_receipts(capsule),
        minimization_receipts=_minimization_receipts(capsule, base),
    )
    return values


def test_canonical_digest_is_stable_and_tampering_is_rejected() -> None:
    first = _snapshot()
    second = CreditSnapshot.with_digest(
        event_marker_count=1,
        event_ledger_total_cents=2_500,
        event_ledger_count=1,
        account_balance_cents=2_500,
    )
    assert first.digest == second.digest

    tampered = first.model_dump(mode="json")
    tampered["account_balance_cents"] = 5_000
    with pytest.raises(ValidationError, match="digest mismatch"):
        CreditSnapshot.model_validate(tampered)


def test_strict_models_reject_extra_fields() -> None:
    payload = _snapshot().model_dump(mode="json")
    payload["candidate_verdict"] = "ACCEPTED"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CreditSnapshot.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("integrity_status", IntegrityStatus.INCOMPLETE),
        ("checkpoint_reached", False),
        ("kill_signal", 15),
        ("replay_acknowledged", False),
    ],
)
def test_completed_attempt_requires_exact_kill_replay_evidence(field: str, value: object) -> None:
    capsule = _capsule()
    values = _attempt_values(capsule, _binding(capsule))
    values[field] = value
    with pytest.raises(ValidationError, match="completed attempt"):
        AttemptReceipt.with_digest(**values)


def test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    attempt = AttemptReceipt.with_digest(**_attempt_values(capsule, binding))
    values = _result_values(capsule, binding, attempt)
    assert CrashCheckResult.with_digest(**values).sweeps[0].observation is (
        CrashObservation.EXACTLY_ONCE
    )

    values["sweeps"] = ()
    with pytest.raises(ValidationError, match="role-specific attempt observations"):
        CrashCheckResult.with_digest(**values)

    values["sweeps"] = (_sweep(capsule, binding, observation=CrashObservation.INVARIANT_FAILED),)
    with pytest.raises(ValidationError, match="role-specific attempt observations"):
        CrashCheckResult.with_digest(**values)
    values["verdict"] = CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN
    assert CrashCheckResult.with_digest(**values).verdict is (
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN
    )


def test_sweep_worlds_are_pinned_to_the_run_and_count_toward_its_axes() -> None:
    """Reviewer findings: sweep worlds were not bound to the run's tree, contract, event, or
    environment digests, and a sweep world's integrity failure did not reach the result's axes."""
    capsule = _capsule()
    binding = _binding(capsule)
    attempt = AttemptReceipt.with_digest(**_attempt_values(capsule, binding))
    values = _result_values(capsule, binding, attempt)
    sweep = cast(tuple[CommitSweepReceipt], values["sweeps"])[0]

    census_values = {
        name: getattr(sweep.census, name)
        for name in NoFaultReplayReceipt.model_fields
        if name != "digest"
    }
    census_values["environment_digest"] = HASHES[8]
    unpinned = CommitSweepReceipt.with_digest(
        **{
            **{n: getattr(sweep, n) for n in CommitSweepReceipt.model_fields if n != "digest"},
            "census": NoFaultReplayReceipt.with_digest(**census_values),
        }
    )
    values["sweeps"] = (unpinned,)
    with pytest.raises(ValidationError, match="not bound to this run"):
        CrashCheckResult.with_digest(**values)

    census_values = {
        name: getattr(sweep.census, name)
        for name in NoFaultReplayReceipt.model_fields
        if name != "digest"
    }
    census_values.update(
        execution_status=ExecutionStatus.INTEGRITY_ERROR,
        integrity_status=IntegrityStatus.INVALID,
        observation=CrashObservation.NOT_OBSERVED,
        failure_detail="rows outside this event changed",
        first_delivery_operations=(),
    )
    broken_census = NoFaultReplayReceipt.with_digest(**census_values)
    broken_sweep = CommitSweepReceipt.with_digest(
        **{
            **{n: getattr(sweep, n) for n in CommitSweepReceipt.model_fields if n != "digest"},
            "census": broken_census,
            "attempts": (),
            "observation": CrashObservation.NOT_OBSERVED,
        }
    )
    values.update(sweeps=(broken_sweep,), verdict=CrashVerdict.EVIDENCE_INCOMPLETE)
    with pytest.raises(ValidationError, match="contradicts its attempts"):
        CrashCheckResult.with_digest(**values)
    values.update(
        integrity_status=IntegrityStatus.INVALID, execution_status=ExecutionStatus.INTEGRITY_ERROR
    )
    assert CrashCheckResult.with_digest(**values).integrity_status is IntegrityStatus.INVALID


def test_commit_sweep_kill_points_must_match_the_census() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    sweep = _sweep(capsule, binding)
    values = {
        name: getattr(sweep, name) for name in CommitSweepReceipt.model_fields if name != "digest"
    }

    values["attempts"] = ()
    with pytest.raises(ValidationError, match="once after each commit"):
        CommitSweepReceipt.with_digest(**values)

    values["attempts"] = sweep.attempts
    values["observation"] = CrashObservation.DUPLICATE_EFFECT
    with pytest.raises(ValidationError, match="sweep observation contradicts"):
        CommitSweepReceipt.with_digest(**values)

    values["observation"] = sweep.observation
    values["role"] = WorldRole.BASE
    with pytest.raises(ValidationError, match="not the base"):
        CommitSweepReceipt.with_digest(**values)


def test_completed_result_cannot_contain_an_incomplete_attempt() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    values = _attempt_values(capsule, binding)
    values.update(
        execution_status=ExecutionStatus.TIMEOUT,
        integrity_status=IntegrityStatus.INCOMPLETE,
        observation=CrashObservation.DUPLICATE_EFFECT,
        failure_detail="worker timed out",
    )
    incomplete = AttemptReceipt.with_digest(**values)

    with pytest.raises(ValidationError, match="result execution status contradicts"):
        CrashCheckResult.with_digest(**_result_values(capsule, binding, incomplete))


def test_duplicate_observation_accepts_a_missing_marker() -> None:
    """Two credits are a duplicate even when the handler never wrote its marker."""
    capsule = _capsule()
    values = _attempt_values(
        capsule, _binding(capsule), observation=CrashObservation.DUPLICATE_EFFECT
    )
    values["final_snapshot"] = _snapshot(effects=2, marker=0)
    receipt = AttemptReceipt.with_digest(**values)
    assert receipt.observation is CrashObservation.DUPLICATE_EFFECT

    values["final_snapshot"] = _snapshot(effects=3, marker=0)
    with pytest.raises(ValidationError, match="observation contradicts its final state"):
        AttemptReceipt.with_digest(**values)


def test_invariant_broken_verdict_requires_unanimous_invariant_failures() -> None:
    capsule = _capsule()
    base = _binding(capsule, source_ref="fixture:base", tree_digest=HASHES[4])
    candidate = _binding(capsule, source_ref="fixture:candidate", tree_digest=HASHES[5])
    base_attempt = AttemptReceipt.with_digest(
        **_attempt_values(
            capsule, base, role=WorldRole.BASE, observation=CrashObservation.DUPLICATE_EFFECT
        )
    )

    def broken(index: int) -> AttemptReceipt:
        values = _attempt_values(capsule, candidate, role=WorldRole.CANDIDATE, index=index)
        values.update(
            observation=CrashObservation.INVARIANT_FAILED, final_snapshot=_snapshot(effects=3)
        )
        return AttemptReceipt.with_digest(**values)

    values = _result_values(capsule, candidate, broken(1))
    values.update(
        verdict=CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN,
        bindings=(base, candidate),
        attempts=(
            *_confirmations(capsule, base, base_attempt),
            *(broken(index) for index in range(1, REQUIRED_CONFIRMATIONS + 1)),
        ),
        hypothesis_receipts=_hypothesis_receipts(capsule),
        minimization_receipts=_minimization_receipts(capsule, base),
    )
    result = CrashCheckResult.with_digest(**values)
    assert result.verdict is CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN

    for wrong in (
        CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE,
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES,
    ):
        values["verdict"] = wrong
        with pytest.raises(ValidationError, match="role-specific attempt observations"):
            CrashCheckResult.with_digest(**values)


def test_completed_attempt_binds_tree_and_observation_to_snapshots() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    assert AttemptReceipt.with_digest(**_attempt_values(capsule, binding))
    assert AttemptReceipt.with_digest(
        **_attempt_values(
            capsule,
            binding,
            observation=CrashObservation.DUPLICATE_EFFECT,
        )
    )

    wrong_tree = _attempt_values(capsule, binding)
    wrong_tree["post_execution_tree_digest"] = HASHES[5]
    with pytest.raises(ValidationError, match="post-execution tree"):
        AttemptReceipt.with_digest(**wrong_tree)

    # The checkpoint is whatever the handler had committed when killed; a commit-sweep kill
    # after a marker-only commit is a legitimate (0, 0, 0, 1) checkpoint.
    marker_only = _attempt_values(capsule, binding, observation=CrashObservation.INVARIANT_FAILED)
    marker_only["checkpoint_snapshot"] = _snapshot(effects=0, marker=1)
    marker_only["post_kill_snapshot"] = marker_only["checkpoint_snapshot"]
    marker_only["final_snapshot"] = _snapshot(effects=0, marker=1)
    assert AttemptReceipt.with_digest(**marker_only).observation is (
        CrashObservation.INVARIANT_FAILED
    )

    wrong_exact_final = _attempt_values(capsule, binding)
    wrong_exact_final["final_snapshot"] = _snapshot(effects=2)
    with pytest.raises(ValidationError, match="observation contradicts its final state"):
        AttemptReceipt.with_digest(**wrong_exact_final)

    wrong_duplicate = _attempt_values(
        capsule,
        binding,
        observation=CrashObservation.DUPLICATE_EFFECT,
    )
    wrong_duplicate["final_snapshot"] = _snapshot()
    with pytest.raises(ValidationError, match="observation contradicts its final state"):
        AttemptReceipt.with_digest(**wrong_duplicate)
    wrong_amount = _attempt_values(capsule, binding)
    wrong_amount["amount_cents"] = 1_000
    with pytest.raises(ValidationError, match="observation contradicts its final state"):
        AttemptReceipt.with_digest(**wrong_amount)

    changed_after_kill = _attempt_values(capsule, binding)
    changed_after_kill["post_kill_snapshot"] = _snapshot(effects=2)
    with pytest.raises(ValidationError, match="checkpoint changed"):
        AttemptReceipt.with_digest(**changed_after_kill)


@pytest.mark.parametrize("field", ["tree_digest", "contract_digest"])
def test_result_attempt_must_match_its_exact_anchor_binding(field: str) -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    values = _attempt_values(capsule, binding)
    values[field] = HASHES[8]
    if field == "tree_digest":
        values["post_execution_tree_digest"] = HASHES[8]
    attempt = AttemptReceipt.with_digest(**values)

    with pytest.raises(ValidationError, match="tree or contract differs"):
        CrashCheckResult.with_digest(**_result_values(capsule, binding, attempt))


def test_result_rejects_duplicate_or_role_ambiguous_anchor_bindings() -> None:
    capsule = _capsule()
    first = _binding(capsule)
    first_attempt = AttemptReceipt.with_digest(**_attempt_values(capsule, first))
    values = _result_values(capsule, first, first_attempt)
    values["bindings"] = (first, first)
    with pytest.raises(ValidationError, match="binding digests must be unique"):
        CrashCheckResult.with_digest(**values)

    second = _binding(
        capsule,
        source_ref="fixture:sqlite-credit-v1/atomic",
        tree_digest=HASHES[5],
    )
    second_attempt = AttemptReceipt.with_digest(**_attempt_values(capsule, second))
    values["bindings"] = (first, second)
    values["attempts"] = (first_attempt, second_attempt)
    with pytest.raises(ValidationError, match="one exact mapping"):
        CrashCheckResult.with_digest(**values)


def test_role_aware_verdicts_require_matching_completed_observations() -> None:
    capsule = _capsule()
    base = _binding(capsule, source_ref="fixture:base", tree_digest=HASHES[4])
    candidate = _binding(capsule, source_ref="fixture:candidate", tree_digest=HASHES[5])
    base_duplicate = AttemptReceipt.with_digest(
        **_attempt_values(
            capsule,
            base,
            role=WorldRole.BASE,
            observation=CrashObservation.DUPLICATE_EFFECT,
        )
    )
    candidate_exact = AttemptReceipt.with_digest(
        **_attempt_values(capsule, candidate, role=WorldRole.CANDIDATE)
    )
    base_attempts = _confirmations(capsule, base, base_duplicate)
    candidate_exact_attempts = _confirmations(capsule, candidate, candidate_exact)
    values = _result_values(capsule, candidate, candidate_exact)
    values.update(
        bindings=(base, candidate),
        attempts=(*base_attempts, *candidate_exact_attempts),
        hypothesis_receipts=_hypothesis_receipts(capsule),
        minimization_receipts=_minimization_receipts(capsule, base),
    )
    result = CrashCheckResult.with_digest(**values)
    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    hunt_receipts = values["hypothesis_receipts"]
    values["hypothesis_receipts"] = ()
    values["minimization_receipts"] = ()
    with pytest.raises(ValidationError, match="conclusive full check"):
        CrashCheckResult.with_digest(**values)
    values["hypothesis_receipts"] = hunt_receipts
    values["minimization_receipts"] = _minimization_receipts(capsule, base)

    candidate_duplicate = AttemptReceipt.with_digest(
        **_attempt_values(
            capsule,
            candidate,
            role=WorldRole.CANDIDATE,
            observation=CrashObservation.DUPLICATE_EFFECT,
        )
    )
    candidate_duplicate_attempts = _confirmations(capsule, candidate, candidate_duplicate)
    values["attempts"] = (*base_attempts, *candidate_duplicate_attempts)
    with pytest.raises(ValidationError, match="role-specific attempt observations"):
        CrashCheckResult.with_digest(**values)

    values["verdict"] = CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    result = CrashCheckResult.with_digest(**values)
    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES


def test_conclusive_verdict_requires_five_confirmations_per_role() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    first = AttemptReceipt.with_digest(**_attempt_values(capsule, binding))
    values = _result_values(capsule, binding, first)
    assert len(cast(tuple[AttemptReceipt, ...], values["attempts"])) == REQUIRED_CONFIRMATIONS

    values["attempts"] = cast(tuple[AttemptReceipt, ...], values["attempts"])[:-1]
    with pytest.raises(ValidationError, match="5 attempts per claimed role"):
        CrashCheckResult.with_digest(**values)

    values["verdict"] = CrashVerdict.EVIDENCE_INCOMPLETE
    assert len(CrashCheckResult.with_digest(**values).attempts) == REQUIRED_CONFIRMATIONS - 1


@pytest.mark.parametrize(
    "field", ["database_id", "execution_nonce", "worker_nonce", "ipc_session_id"]
)
def test_conclusive_verdict_requires_globally_fresh_attempt_identities(field: str) -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    first = AttemptReceipt.with_digest(**_attempt_values(capsule, binding))
    attempts = list(_confirmations(capsule, binding, first))
    second_values = _attempt_values(capsule, binding, index=2)
    if field in {"database_id", "execution_nonce"}:
        second_values[field] = getattr(first, field)
    else:
        spawns = cast(tuple[WorkerSpawnReceipt, WorkerSpawnReceipt], second_values["spawns"])
        second_values["spawns"] = (
            spawns[0].model_copy(update={field: getattr(first.spawns[0], field)}),
            spawns[1],
        )
    attempts[1] = AttemptReceipt.with_digest(**second_values)
    values = _result_values(capsule, binding, first)
    values["attempts"] = tuple(attempts)

    with pytest.raises(ValidationError, match="globally unique"):
        CrashCheckResult.with_digest(**values)


def test_engine_source_commit_is_bounded_and_tamper_evident() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    attempt = AttemptReceipt.with_digest(**_attempt_values(capsule, binding))
    values = _result_values(capsule, binding, attempt)
    result = CrashCheckResult.with_digest(**values)
    assert result.engine_source_commit == "a" * 40

    tampered = result.model_dump(mode="json")
    tampered["engine_source_commit"] = "b" * 40
    with pytest.raises(ValidationError, match="digest mismatch"):
        CrashCheckResult.model_validate_json(canonical_json(tampered))

    values["engine_source_commit"] = "a" * 40 + "-dirty"
    assert CrashCheckResult.with_digest(**values).engine_source_commit == "a" * 40 + "-dirty"
    values["engine_source_commit"] = None
    assert CrashCheckResult.with_digest(**values).engine_source_commit is None
    values["engine_source_commit"] = "not-a-commit"
    with pytest.raises(ValidationError, match="String should match pattern"):
        CrashCheckResult.with_digest(**values)


def test_worker_and_attempt_timestamps_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="worker execution ended before it started"):
        WorkerSpawnReceipt(
            **{
                **_worker(1, "first", nonce="worker-1", session="session-1").model_dump(),
                "ended_at": NOW - timedelta(seconds=1),
            }
        )

    capsule = _capsule()
    values = _attempt_values(capsule, _binding(capsule))
    values["ended_at"] = NOW - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="attempt ended before it started"):
        AttemptReceipt.with_digest(**values)

    valid_attempt = AttemptReceipt.with_digest(**_attempt_values(capsule, _binding(capsule)))
    result_values = _result_values(capsule, _binding(capsule), valid_attempt)
    result_values["ended_at"] = NOW - timedelta(seconds=1)
    with pytest.raises(ValidationError, match="result ended before it started"):
        CrashCheckResult.with_digest(**result_values)


@pytest.mark.parametrize("duplicate", ["nonce", "session"])
def test_replay_worker_requires_distinct_nonce_and_session(duplicate: str) -> None:
    capsule = _capsule()
    values = _attempt_values(capsule, _binding(capsule))
    nonce = "worker-1" if duplicate == "nonce" else "worker-2"
    session = "session-1" if duplicate == "session" else "session-2"
    values["spawns"] = (
        _worker(1, "first", nonce="worker-1", session="session-1"),
        _worker(2, "replay", nonce=nonce, session=session),
    )
    with pytest.raises(ValidationError, match="must be distinct"):
        AttemptReceipt.with_digest(**values)


@pytest.mark.parametrize("field", ["source_ref", "resolved_source_identity"])
def test_anchor_source_identity_fields_are_required(field: str) -> None:
    payload = _binding(_capsule()).model_dump(mode="json")
    del payload[field]
    with pytest.raises(ValidationError, match="Field required"):
        AnchorBinding.model_validate(payload)


@pytest.mark.parametrize("field", ["source_ref", "resolved_source_identity"])
def test_anchor_source_identity_fields_are_bounded(field: str) -> None:
    values = _binding(_capsule()).model_dump(mode="python", exclude={"digest"})
    values[field] = "x" * 500
    assert getattr(AnchorBinding.with_digest(**values), field) == "x" * 500

    for invalid in ("", "x" * 501):
        values[field] = invalid
        with pytest.raises(ValidationError):
            AnchorBinding.with_digest(**values)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("source_ref", "fixture:sqlite-credit-v1/atomic"),
        ("resolved_source_identity", HASHES[8]),
    ],
)
def test_anchor_source_identity_is_canonical_and_tamper_evident(
    field: str, replacement: str
) -> None:
    binding = _binding(_capsule())
    values = binding.model_dump(mode="python", exclude={"digest"})
    reordered = dict(reversed(tuple(values.items())))
    assert AnchorBinding.with_digest(**reordered).digest == binding.digest

    values[field] = replacement
    assert AnchorBinding.with_digest(**values).digest != binding.digest

    tampered = binding.model_dump(mode="json")
    tampered[field] = replacement
    with pytest.raises(ValidationError, match="digest mismatch"):
        AnchorBinding.model_validate(tampered)


@pytest.mark.parametrize("path", ["../app/credits.py", "/tmp/credits.py"])
def test_anchor_binding_rejects_unsafe_handler_paths(path: str) -> None:
    capsule = _capsule()
    with pytest.raises(ValidationError, match="unsafe path"):
        AnchorBinding.with_digest(
            contract_digest=capsule.contract_digest,
            scenario_id=capsule.scenario_id,
            source_ref="fixture:sqlite-credit-v1/buggy",
            resolved_source_identity="fixture:sqlite-credit-v1/buggy",
            tree_digest=HASHES[4],
            handler_path=path,
            handler_symbol="apply_credit",
            adapter_id="sqlite-credit-v1",
            fault_intent_id=capsule.fault_intent_id,
        )


def test_capsule_event_fields_are_bound_to_the_event_digest() -> None:
    capsule = _capsule()
    values = capsule.model_dump(mode="python", exclude={"digest"})
    values["amount_cents"] = 5_000
    with pytest.raises(ValidationError, match="capsule event digest mismatch"):
        ReproCapsule.with_digest(**values)


def test_hypothesis_receipt_is_strict_digest_bound_base_evidence() -> None:
    capsule = _capsule()
    receipt = _hypothesis_receipts(capsule)[0]
    values = _hypothesis_values(receipt)
    assert HypothesisReceipt.with_digest(**dict(reversed(tuple(values.items())))).digest == (
        receipt.digest
    )

    tampered = receipt.model_dump(mode="json")
    tampered["selected"] = False
    with pytest.raises(ValidationError, match="digest mismatch"):
        HypothesisReceipt.model_validate_json(canonical_json(tampered))

    values["attempt"] = AttemptReceipt.with_digest(
        **_attempt_values(capsule, _binding(capsule), role=WorldRole.CANDIDATE)
    )
    with pytest.raises(ValidationError, match="BASE/LOCAL"):
        HypothesisReceipt.with_digest(**values)


def test_minimization_receipt_binds_trace_and_fresh_confirmations() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    receipt = _minimization_receipts(capsule, binding)[0]
    assert receipt.schema_version == "2"
    assert receipt.sole_fault_action_necessary_for_fixture
    serialized = receipt.model_dump(mode="json")
    assert not {"irreducible", "reproduced", "retained"} & serialized.keys()
    values = {
        name: getattr(receipt, name)
        for name in MinimizationReceipt.model_fields
        if name != "digest"
    }
    values["trace_digest"] = HASHES[8]
    with pytest.raises(ValidationError, match="deletion trace digest mismatch"):
        MinimizationReceipt.with_digest(**values)

    missing_database_digest = {
        name: getattr(receipt.confirmations[0], name)
        for name in NoFaultReplayReceipt.model_fields
        if name != "digest"
    }
    missing_database_digest["initial_database_file_digest"] = None
    with pytest.raises(ValidationError, match="completed no-fault replay"):
        NoFaultReplayReceipt.with_digest(**missing_database_digest)

    values = {
        name: getattr(receipt, name)
        for name in MinimizationReceipt.model_fields
        if name != "digest"
    }
    confirmations = list(receipt.confirmations)
    duplicate_values = {
        name: getattr(confirmations[1], name)
        for name in NoFaultReplayReceipt.model_fields
        if name != "digest"
    }
    duplicate_values["database_id"] = confirmations[0].database_id
    confirmations[1] = NoFaultReplayReceipt.with_digest(**duplicate_values)
    values["confirmations"] = tuple(confirmations)
    with pytest.raises(ValidationError, match="fresh execution identities"):
        MinimizationReceipt.with_digest(**values)


def test_hypothesis_receipt_requires_local_attempt() -> None:
    capsule = _capsule()
    attempt_values = _attempt_values(capsule, _binding(capsule), role=WorldRole.BASE, index=101)
    attempt_values["transport"] = TruthLabel.LIVE
    values = _hypothesis_values(_hypothesis_receipts(capsule)[0])
    values["attempt"] = AttemptReceipt.with_digest(**attempt_values)
    with pytest.raises(ValidationError, match="BASE/LOCAL"):
        HypothesisReceipt.with_digest(**values)


def test_hypothesis_receipt_records_terminal_failure_but_conclusive_result_rejects_it() -> None:
    capsule = _capsule()
    attempt_values = _attempt_values(capsule, _binding(capsule), role=WorldRole.BASE, index=101)
    attempt_values.update(
        execution_status=ExecutionStatus.TIMEOUT,
        integrity_status=IntegrityStatus.INCOMPLETE,
        observation=CrashObservation.NOT_OBSERVED,
        failure_detail="worker timed out",
    )
    values = _hypothesis_values(_hypothesis_receipts(capsule)[0])
    values.update(
        reproduced=False,
        selected=False,
        attempt=AttemptReceipt.with_digest(**attempt_values),
    )
    failed = HypothesisReceipt.with_digest(**values)
    assert failed.reproduced is False

    result_values = _full_result_values(capsule)
    receipts = cast(
        tuple[HypothesisReceipt, HypothesisReceipt], result_values["hypothesis_receipts"]
    )
    result_values["hypothesis_receipts"] = (failed, receipts[1])
    result_values["minimization_receipts"] = ()
    result_values["verdict"] = CrashVerdict.EVIDENCE_INCOMPLETE
    assert CrashCheckResult.with_digest(**result_values).hypothesis_receipts[0] == failed
    result_values["verdict"] = CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    with pytest.raises(ValidationError, match="completed valid hypothesis attempts"):
        CrashCheckResult.with_digest(**result_values)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("hypothesis_id", "unknown-v1"),
        ("fault_boundary", FaultBoundary.MARKER_COMMIT),
        ("trusted_operation_count", 2),
    ],
)
def test_hypothesis_receipt_enforces_trusted_catalog(field: str, replacement: object) -> None:
    values = _hypothesis_values(_hypothesis_receipts(_capsule())[0])
    values[field] = replacement
    with pytest.raises(ValidationError, match="trusted catalog"):
        HypothesisReceipt.with_digest(**values)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("contract_digest", HASHES[8]),
        ("originating_base_tree_digest", HASHES[8]),
        ("provisional_capsule_digest", HASHES[8]),
    ],
)
def test_hypothesis_receipt_links_exact_inputs(field: str, replacement: str) -> None:
    values = _hypothesis_values(_hypothesis_receipts(_capsule())[0])
    values[field] = replacement
    with pytest.raises(ValidationError, match="exact contract, tree, or capsule"):
        HypothesisReceipt.with_digest(**values)

    values = _hypothesis_values(_hypothesis_receipts(_capsule())[0])
    values["reproduced"] = False
    with pytest.raises(ValidationError, match="reproduced flag"):
        HypothesisReceipt.with_digest(**values)


def test_conclusive_result_requires_canonical_deterministic_hypothesis_selection() -> None:
    capsule = _capsule()
    values = _full_result_values(capsule)
    receipts = cast(tuple[HypothesisReceipt, HypothesisReceipt], values["hypothesis_receipts"])
    values["hypothesis_receipts"] = tuple(reversed(receipts))
    with pytest.raises(ValidationError, match="both canonical crash-boundary"):
        CrashCheckResult.with_digest(**values)

    duplicate_rank = _hypothesis_values(receipts[1])
    duplicate_rank["canonical_rank"] = 1
    with pytest.raises(ValidationError, match="trusted catalog"):
        HypothesisReceipt.with_digest(**duplicate_rank)

    first = _hypothesis_values(receipts[0])
    second = _hypothesis_values(receipts[1])
    first["selected"] = False
    second.update(
        reproduced=True,
        selected=True,
        attempt=AttemptReceipt.with_digest(
            **_attempt_values(
                _capsule_for_boundary(FaultBoundary.MARKER_COMMIT),
                _binding(_capsule_for_boundary(FaultBoundary.MARKER_COMMIT)),
                role=WorldRole.BASE,
                observation=CrashObservation.DUPLICATE_EFFECT,
                index=102,
            )
        ),
    )
    values["hypothesis_receipts"] = (
        HypothesisReceipt.with_digest(**first),
        HypothesisReceipt.with_digest(**second),
    )
    values["minimization_receipts"] = ()
    with pytest.raises(ValidationError, match="deterministic ordering"):
        CrashCheckResult.with_digest(**values)


@pytest.mark.parametrize("field", ["contract_digest", "originating_base_tree_digest"])
def test_hypothesis_receipts_match_exact_base_binding(field: str) -> None:
    capsule = _capsule()
    hunt_values = capsule.model_dump(mode="python", exclude={"digest"})
    hunt_values[field] = HASHES[8]
    hunt_capsule = ReproCapsule.with_digest(**hunt_values)
    values = _full_result_values(capsule)
    values["hypothesis_receipts"] = _hypothesis_receipts(hunt_capsule)
    with pytest.raises(ValidationError, match="differ from the BASE binding"):
        CrashCheckResult.with_digest(**values)


@pytest.mark.parametrize("field", ["database_id", "receipt_id"])
def test_hypothesis_attempt_identities_are_unique(field: str) -> None:
    values = _full_result_values(_capsule())
    receipts = cast(tuple[HypothesisReceipt, HypothesisReceipt], values["hypothesis_receipts"])
    attempt_values = _attempt_receipt_values(receipts[1].attempt)
    attempt_values[field] = getattr(receipts[0].attempt, field)
    second_values = _hypothesis_values(receipts[1])
    second_values["attempt"] = AttemptReceipt.with_digest(**attempt_values)
    values["hypothesis_receipts"] = (
        receipts[0],
        HypothesisReceipt.with_digest(**second_values),
    )
    with pytest.raises(ValidationError, match="unique hunt identities"):
        CrashCheckResult.with_digest(**values)


def test_hypothesis_provisional_capsules_are_unique() -> None:
    values = _full_result_values(_capsule())
    receipts = cast(tuple[HypothesisReceipt, HypothesisReceipt], values["hypothesis_receipts"])
    attempt_values = _attempt_receipt_values(receipts[1].attempt)
    attempt_values["capsule_digest"] = receipts[0].provisional_capsule_digest
    second_values = _hypothesis_values(receipts[1])
    second_values.update(
        provisional_capsule_digest=receipts[0].provisional_capsule_digest,
        attempt=AttemptReceipt.with_digest(**attempt_values),
    )
    values["hypothesis_receipts"] = (
        receipts[0],
        HypothesisReceipt.with_digest(**second_values),
    )
    with pytest.raises(ValidationError, match="unique hunt identities"):
        CrashCheckResult.with_digest(**values)


def test_hypothesis_and_proof_attempt_identities_do_not_overlap() -> None:
    values = _full_result_values(_capsule())
    receipts = cast(tuple[HypothesisReceipt, HypothesisReceipt], values["hypothesis_receipts"])
    proof_attempts = cast(tuple[AttemptReceipt, ...], values["attempts"])
    attempt_values = _attempt_receipt_values(receipts[0].attempt)
    attempt_values["database_id"] = proof_attempts[0].database_id
    first_values = _hypothesis_values(receipts[0])
    first_values["attempt"] = AttemptReceipt.with_digest(**attempt_values)
    values["hypothesis_receipts"] = (
        HypothesisReceipt.with_digest(**first_values),
        receipts[1],
    )
    with pytest.raises(ValidationError, match="disjoint identities"):
        CrashCheckResult.with_digest(**values)


def test_incomplete_live_result_can_omit_hypothesis_receipts() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    attempt = AttemptReceipt.with_digest(
        **_attempt_values(capsule, binding, transport=TruthLabel.LIVE)
    )
    values = _result_values(capsule, binding, attempt)
    values.update(
        transport=TruthLabel.LIVE,
        verdict=CrashVerdict.EVIDENCE_INCOMPLETE,
        attempts=_confirmations(capsule, binding, attempt),
        hypothesis_receipts=(),
    )
    assert CrashCheckResult.with_digest(**values).hypothesis_receipts == ()

    values.update(
        transport=TruthLabel.LOCAL,
        verdict=CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE,
        attempts=_confirmations(
            capsule,
            binding,
            AttemptReceipt.with_digest(**_attempt_values(capsule, binding)),
        ),
        sweeps=(_sweep(capsule, binding),),
    )
    assert CrashCheckResult.with_digest(**values).hypothesis_receipts == ()


def test_engine_digest_is_required_and_changes_capsule_and_result_digests() -> None:
    capsule = _capsule()
    values = capsule.model_dump(mode="python", exclude={"digest"})
    values["engine_code_digest"] = HASHES[8]
    assert ReproCapsule.with_digest(**values).digest != capsule.digest
    del values["engine_code_digest"]
    with pytest.raises(ValidationError, match="Field required"):
        ReproCapsule.with_digest(**values)

    binding = _binding(capsule)
    attempt = AttemptReceipt.with_digest(**_attempt_values(capsule, binding))
    result = CrashCheckResult.with_digest(**_result_values(capsule, binding, attempt))
    values = {
        name: getattr(result, name) for name in CrashCheckResult.model_fields if name != "digest"
    }
    del values["engine_code_digest"]
    with pytest.raises(ValidationError, match="Field required"):
        CrashCheckResult.with_digest(**values)


def test_result_artifacts_must_be_portable_relative_paths() -> None:
    capsule = _capsule()
    binding = _binding(capsule)
    attempt = AttemptReceipt.with_digest(**_attempt_values(capsule, binding))
    values = _result_values(capsule, binding, attempt)
    values["artifacts"] = {"capsule": "/tmp/capsule.json"}

    with pytest.raises(ValidationError, match="unsafe path"):
        CrashCheckResult.with_digest(**values)
