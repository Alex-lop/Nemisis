"""Strict evidence contracts for the CrashCheck SQLite vertical slice."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from nemisis.hashing import canonical_json, sha256_json
from nemisis.models import SafeId, Sha256, StrictModel, TruthLabel
from nemisis.safety import safe_relative_path

REQUIRED_CONFIRMATIONS = 5


class WorldRole(StrEnum):
    BASE = "base"
    CANDIDATE = "candidate"
    CORRECTED = "corrected"


class ExecutionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    SETUP_ERROR = "SETUP_ERROR"
    LAUNCH_ERROR = "LAUNCH_ERROR"
    IPC_ERROR = "IPC_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    CHECKPOINT_NOT_REACHED = "CHECKPOINT_NOT_REACHED"
    PROBE_ERROR = "PROBE_ERROR"
    KILL_ERROR = "KILL_ERROR"
    WAIT_ERROR = "WAIT_ERROR"
    RESTART_ERROR = "RESTART_ERROR"
    REPLAY_ERROR = "REPLAY_ERROR"
    TIMEOUT = "TIMEOUT"
    INTEGRITY_ERROR = "INTEGRITY_ERROR"
    CLEANUP_ERROR = "CLEANUP_ERROR"
    UNSUPPORTED = "UNSUPPORTED"


class IntegrityStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"


class CrashObservation(StrEnum):
    DUPLICATE_EFFECT = "DUPLICATE_EFFECT"
    EXACTLY_ONCE = "EXACTLY_ONCE"
    INVARIANT_FAILED = "INVARIANT_FAILED"
    NOT_OBSERVED = "NOT_OBSERVED"


class CrashVerdict(StrEnum):
    BUG_REPRODUCED = "BUG_REPRODUCED"
    PATCH_FAILED_STILL_REPRODUCES = "PATCH_FAILED_STILL_REPRODUCES"
    FIX_PROVEN_FOR_THIS_CAPSULE = "FIX_PROVEN_FOR_THIS_CAPSULE"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    UNSUPPORTED_TARGET = "UNSUPPORTED_TARGET"


class FaultBoundary(StrEnum):
    EFFECT_COMMIT = "effect-commit"
    MARKER_COMMIT = "marker-commit"


class TimelineState(StrEnum):
    PREFLIGHT = "PREFLIGHT"
    DATABASE_SEEDED = "DATABASE_SEEDED"
    PRE_CRASH_PROBED = "PRE_CRASH_PROBED"
    FIRST_WORKER_STARTED = "FIRST_WORKER_STARTED"
    CHECKPOINT_REACHED = "CHECKPOINT_REACHED"
    WORKER_KILLED = "WORKER_KILLED"
    POST_KILL_PROBED = "POST_KILL_PROBED"
    REPLAY_WORKER_STARTED = "REPLAY_WORKER_STARTED"
    EVENT_REPLAYED = "EVENT_REPLAYED"
    FINAL_STATE_PROBED = "FINAL_STATE_PROBED"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class _DigestedModel(StrictModel):
    digest: Sha256

    @classmethod
    def with_digest(cls, **values: object) -> Self:
        unvalidated = cls.model_construct(_fields_set=None, digest="0" * 64, **values)
        payload = unvalidated.model_dump(mode="json", exclude={"digest"})
        payload["digest"] = sha256_json(payload)
        return cls.model_validate_json(canonical_json(payload))

    @model_validator(mode="after")
    def canonical_digest_matches(self) -> Self:
        self._require_canonical_digest()
        return self

    def _require_canonical_digest(self) -> None:
        payload = self.model_dump(mode="json", exclude={"digest"})
        if sha256_json(payload) != self.digest:
            raise ValueError(f"{type(self).__name__} digest mismatch")


class RetryContract(_DigestedModel):
    """Candidate-blind, accepted promise compiled only from trusted catalog IDs."""

    schema_version: Literal["1"] = "1"
    scenario_id: SafeId
    originating_base_ref: str = Field(min_length=1, max_length=200)
    originating_base_tree_digest: Sha256
    issue_digest: Sha256
    target: str = Field(
        min_length=3,
        max_length=240,
        pattern=r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$",
    )
    adapter_id: SafeId
    event_fixture_id: SafeId
    event_digest: Sha256
    fault_intent_id: SafeId
    probe_id: SafeId
    predicate_ids: tuple[SafeId, ...] = Field(min_length=1, max_length=8)
    accepted: bool
    truth_label: TruthLabel

    @model_validator(mode="after")
    def predicates_are_unique(self) -> RetryContract:
        if len(set(self.predicate_ids)) != len(self.predicate_ids):
            raise ValueError("predicate IDs must be unique")
        return self


class AnchorBinding(_DigestedModel):
    """One deterministic handler mapping bound to one exact source tree."""

    schema_version: Literal["1"] = "1"
    contract_digest: Sha256
    scenario_id: SafeId
    source_ref: str = Field(min_length=1, max_length=500)
    resolved_source_identity: str = Field(min_length=1, max_length=500)
    tree_digest: Sha256
    handler_path: str = Field(
        min_length=4,
        max_length=240,
        pattern=r"^[A-Za-z0-9_./-]+\.py$",
    )
    handler_symbol: SafeId
    adapter_id: SafeId
    fault_intent_id: SafeId

    @model_validator(mode="after")
    def handler_path_is_safe(self) -> AnchorBinding:
        safe_relative_path(self.handler_path)
        return self


class CreditSnapshot(_DigestedModel):
    account_balance_cents: int
    event_ledger_count: int = Field(ge=0)
    event_ledger_total_cents: int
    event_marker_count: int = Field(ge=0, le=1)


class TimelineEntry(StrictModel):
    state: TimelineState
    timestamp: datetime
    detail: str = Field(default="", max_length=500)


class WorkerSpawnReceipt(StrictModel):
    spawn_index: int = Field(ge=1, le=2)
    phase: Literal["first", "replay"]
    pid: int = Field(gt=0)
    process_group_id: int = Field(gt=0)
    worker_nonce: SafeId
    ipc_session_id: SafeId
    event_digest: Sha256
    started_at: datetime
    ended_at: datetime
    exit_code: int
    stdout_excerpt: str = Field(max_length=4_000)
    stderr_excerpt: str = Field(max_length=4_000)
    stdout_digest: Sha256
    stderr_digest: Sha256

    @model_validator(mode="after")
    def timestamps_are_ordered(self) -> WorkerSpawnReceipt:
        if self.ended_at < self.started_at:
            raise ValueError("worker execution ended before it started")
        return self


class AttemptReceipt(_DigestedModel):
    """Volatile observations for one fresh database and exact source tree."""

    schema_version: Literal["1"] = "1"
    receipt_id: SafeId
    role: WorldRole
    transport: TruthLabel
    execution_status: ExecutionStatus
    integrity_status: IntegrityStatus
    observation: CrashObservation
    capsule_digest: Sha256
    contract_digest: Sha256
    binding_digest: Sha256
    tree_digest: Sha256
    post_execution_tree_digest: Sha256 | None = None
    environment_digest: Sha256
    event_digest: Sha256
    initial_database_digest: Sha256
    initial_database_file_digest: Sha256 | None = None
    database_id: SafeId
    execution_nonce: SafeId
    started_at: datetime
    ended_at: datetime
    timeline: tuple[TimelineEntry, ...] = Field(min_length=1, max_length=32)
    spawns: tuple[WorkerSpawnReceipt, ...] = Field(max_length=2)
    pre_crash_snapshot: CreditSnapshot | None = None
    checkpoint_snapshot: CreditSnapshot | None = None
    post_kill_snapshot: CreditSnapshot | None = None
    final_snapshot: CreditSnapshot | None = None
    checkpoint_reached: bool
    kill_signal: int | None = None
    replay_acknowledged: bool
    failure_detail: str | None = Field(default=None, max_length=1_000)
    provider_operation_id: str | None = Field(default=None, max_length=200)
    provider_image_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def evidence_is_coherent(self) -> AttemptReceipt:
        if self.ended_at < self.started_at:
            raise ValueError("attempt ended before it started")
        timestamps = [entry.timestamp for entry in self.timeline]
        if timestamps != sorted(timestamps):
            raise ValueError("attempt timeline is not ordered")
        if len({spawn.spawn_index for spawn in self.spawns}) != len(self.spawns):
            raise ValueError("worker spawn indices must be unique")
        if any(spawn.event_digest != self.event_digest for spawn in self.spawns):
            raise ValueError("worker event digest differs from attempt event")
        if len(self.spawns) == 2:
            if len({spawn.worker_nonce for spawn in self.spawns}) != 2:
                raise ValueError("worker nonces must be distinct")
            if len({spawn.ipc_session_id for spawn in self.spawns}) != 2:
                raise ValueError("IPC sessions must be distinct")
        for snapshot in (
            self.pre_crash_snapshot,
            self.checkpoint_snapshot,
            self.post_kill_snapshot,
            self.final_snapshot,
        ):
            if snapshot is not None:
                snapshot._require_canonical_digest()
        if self.execution_status is ExecutionStatus.COMPLETED:
            if self.integrity_status is not IntegrityStatus.VALID:
                raise ValueError("completed attempt requires valid integrity")
            if self.failure_detail is not None:
                raise ValueError("completed attempt cannot have a failure detail")
            if not (
                self.checkpoint_reached
                and self.kill_signal == 9
                and self.replay_acknowledged
                and self.pre_crash_snapshot is not None
                and self.checkpoint_snapshot is not None
                and self.post_kill_snapshot is not None
                and self.final_snapshot is not None
                and len(self.spawns) == 2
                and self.spawns[0].phase == "first"
                and self.spawns[0].exit_code == -9
                and self.spawns[1].phase == "replay"
                and self.spawns[1].exit_code == 0
            ):
                raise ValueError("completed attempt lacks exact kill/replay evidence")
            if self.post_execution_tree_digest != self.tree_digest:
                raise ValueError(
                    "completed attempt post-execution tree differs from its bound tree"
                )
            pre = self.pre_crash_snapshot
            checkpoint = self.checkpoint_snapshot
            post_kill = self.post_kill_snapshot
            final = self.final_snapshot
            assert pre is not None and checkpoint is not None and post_kill is not None
            assert final is not None
            if _snapshot_state(pre) != (0, 0, 0, 0):
                raise ValueError("completed attempt pre-crash snapshot is not the seeded state")
            if post_kill.digest != checkpoint.digest:
                raise ValueError("completed attempt checkpoint changed after worker death")
            checkpoint_state = _snapshot_state(checkpoint)
            final_state = _snapshot_state(final)
            if self.observation is CrashObservation.DUPLICATE_EFFECT:
                expected_checkpoint = (
                    checkpoint.account_balance_cents,
                    1,
                    checkpoint.account_balance_cents,
                    0,
                )
                expected_final = (
                    checkpoint.account_balance_cents * 2,
                    2,
                    checkpoint.account_balance_cents * 2,
                    1,
                )
                if checkpoint.account_balance_cents <= 0 or (
                    checkpoint_state,
                    final_state,
                ) != (expected_checkpoint, expected_final):
                    raise ValueError("duplicate observation contradicts checkpoint or final state")
            elif self.observation is CrashObservation.EXACTLY_ONCE:
                expected = (
                    checkpoint.account_balance_cents,
                    1,
                    checkpoint.account_balance_cents,
                    1,
                )
                if (
                    checkpoint.account_balance_cents <= 0
                    or checkpoint_state != expected
                    or (final_state != expected)
                ):
                    raise ValueError(
                        "exactly-once observation contradicts checkpoint or final state"
                    )
            elif self.observation is CrashObservation.NOT_OBSERVED:
                raise ValueError("completed attempt requires an observed final state")
        elif self.failure_detail is None:
            raise ValueError("incomplete attempt requires a failure detail")
        return self


class ReproCapsule(_DigestedModel):
    """Immutable semantic witness; volatile tree bindings and nonces stay outside it."""

    schema_version: Literal["1"] = "1"
    contract_digest: Sha256
    originating_base_tree_digest: Sha256
    engine_code_digest: Sha256
    scenario_id: SafeId
    scenario_version: SafeId
    event_id: SafeId
    account_id: SafeId
    amount_cents: int = Field(gt=0, le=1_000_000)
    event_digest: Sha256
    fault_intent_id: SafeId
    fault_boundary: FaultBoundary
    probe_id: SafeId
    predicate_ids: tuple[SafeId, ...] = Field(min_length=1, max_length=8)
    runner_id: SafeId
    runner_version: SafeId
    environment_digest: Sha256
    initial_database_digest: Sha256
    minimization_trace: tuple[SafeId, ...] = Field(max_length=16)
    truth_label: TruthLabel

    @model_validator(mode="after")
    def event_and_predicates_are_canonical(self) -> ReproCapsule:
        event = {
            "account_id": self.account_id,
            "amount_cents": self.amount_cents,
            "event_id": self.event_id,
        }
        if sha256_json(event) != self.event_digest:
            raise ValueError("capsule event digest mismatch")
        if len(set(self.predicate_ids)) != len(self.predicate_ids):
            raise ValueError("predicate IDs must be unique")
        return self


class HypothesisReceipt(_DigestedModel):
    """Candidate-blind result for one bounded base-tree hypothesis."""

    schema_version: Literal["1"] = "1"
    canonical_rank: Literal[1, 2]
    hypothesis_id: SafeId
    contract_digest: Sha256
    originating_base_tree_digest: Sha256
    fault_boundary: FaultBoundary
    trusted_operation_count: Literal[1, 2]
    reproduced: bool
    selected: bool
    provisional_capsule_digest: Sha256
    attempt: AttemptReceipt

    @model_validator(mode="after")
    def base_attempt_is_exact(self) -> HypothesisReceipt:
        self.attempt._require_canonical_digest()
        if (
            self.attempt.role is not WorldRole.BASE
            or self.attempt.transport is not TruthLabel.LOCAL
        ):
            raise ValueError("hypothesis receipt requires a BASE/LOCAL attempt")
        catalogs = {
            1: ("effect-commit-v1", FaultBoundary.EFFECT_COMMIT, 1),
            2: ("marker-commit-v1", FaultBoundary.MARKER_COMMIT, 2),
        }
        if (
            self.hypothesis_id,
            self.fault_boundary,
            self.trusted_operation_count,
        ) != catalogs[self.canonical_rank]:
            raise ValueError("hypothesis receipt differs from the trusted catalog")
        if (
            self.attempt.contract_digest != self.contract_digest
            or self.attempt.tree_digest != self.originating_base_tree_digest
            or self.attempt.capsule_digest != self.provisional_capsule_digest
        ):
            raise ValueError(
                "hypothesis receipt does not link its exact contract, tree, or capsule"
            )
        expected_reproduced = (
            self.attempt.execution_status is ExecutionStatus.COMPLETED
            and self.attempt.integrity_status is IntegrityStatus.VALID
            and self.attempt.observation is CrashObservation.DUPLICATE_EFFECT
        )
        if self.reproduced is not expected_reproduced:
            raise ValueError("hypothesis reproduced flag contradicts its attempt")
        return self


class CrashCheckResult(_DigestedModel):
    """Four independent result axes plus the exact receipts supporting the verdict."""

    schema_version: Literal["1"] = "1"
    run_id: SafeId
    transport: TruthLabel
    execution_status: ExecutionStatus
    integrity_status: IntegrityStatus
    verdict: CrashVerdict
    capsule_digest: Sha256
    engine_code_digest: Sha256
    hypothesis_receipts: tuple[HypothesisReceipt, ...] = Field(default=(), max_length=2)
    bindings: tuple[AnchorBinding, ...] = Field(min_length=1, max_length=3)
    attempts: tuple[AttemptReceipt, ...] = Field(min_length=1, max_length=24)
    started_at: datetime
    ended_at: datetime
    summary: str = Field(min_length=1, max_length=1_000)
    engine_source_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40}(?:-dirty)?$")
    artifacts: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def result_bindings_are_coherent(self) -> CrashCheckResult:
        if self.ended_at < self.started_at:
            raise ValueError("CrashCheck result ended before it started")
        if any(attempt.capsule_digest != self.capsule_digest for attempt in self.attempts):
            raise ValueError("attempt uses a different capsule")
        for binding in self.bindings:
            binding._require_canonical_digest()
        for attempt in self.attempts:
            attempt._require_canonical_digest()
        for receipt in self.hypothesis_receipts:
            receipt._require_canonical_digest()
        for artifact_path in self.artifacts.values():
            safe_relative_path(artifact_path)
        binding_digests = [binding.digest for binding in self.bindings]
        if len(binding_digests) != len(set(binding_digests)):
            raise ValueError("anchor binding digests must be unique")
        binding_by_digest = {binding.digest: binding for binding in self.bindings}
        if any(attempt.binding_digest not in binding_digests for attempt in self.attempts):
            raise ValueError("attempt uses an unreported anchor binding")
        if {attempt.binding_digest for attempt in self.attempts} != set(binding_digests):
            raise ValueError("anchor binding has no attempt evidence")
        for attempt in self.attempts:
            binding = binding_by_digest[attempt.binding_digest]
            if (
                attempt.tree_digest != binding.tree_digest
                or attempt.contract_digest != binding.contract_digest
            ):
                raise ValueError("attempt tree or contract differs from its anchor binding")
        role_bindings = {
            role: {attempt.binding_digest for attempt in self.attempts if attempt.role is role}
            for role in WorldRole
            if any(attempt.role is role for attempt in self.attempts)
        }
        if any(len(digests) != 1 for digests in role_bindings.values()) or len(
            set.union(*role_bindings.values())
        ) != len(role_bindings):
            raise ValueError("attempt roles and anchor bindings must have one exact mapping")
        if any(attempt.transport is not self.transport for attempt in self.attempts):
            raise ValueError("attempt transport differs from result transport")
        if self.hypothesis_receipts:
            _validate_hypothesis_receipt_links(
                self.hypothesis_receipts, binding_by_digest, self.attempts
            )
        completed = all(
            attempt.execution_status is ExecutionStatus.COMPLETED for attempt in self.attempts
        )
        if (self.execution_status is ExecutionStatus.COMPLETED) is not completed or (
            not completed
            and self.execution_status not in {attempt.execution_status for attempt in self.attempts}
        ):
            raise ValueError("result execution status contradicts its attempts")
        expected_integrity = (
            IntegrityStatus.INVALID
            if any(attempt.integrity_status is IntegrityStatus.INVALID for attempt in self.attempts)
            else (
                IntegrityStatus.VALID
                if all(
                    attempt.integrity_status is IntegrityStatus.VALID for attempt in self.attempts
                )
                else IntegrityStatus.INCOMPLETE
            )
        )
        if self.integrity_status is not expected_integrity:
            raise ValueError("result integrity status contradicts its attempts")
        if self.verdict in {
            CrashVerdict.BUG_REPRODUCED,
            CrashVerdict.PATCH_FAILED_STILL_REPRODUCES,
            CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE,
        }:
            if not completed or expected_integrity is not IntegrityStatus.VALID:
                raise ValueError("conclusive verdict requires completed valid attempts")
            if self.hypothesis_receipts:
                _validate_conclusive_hypothesis_receipts(self.hypothesis_receipts)
            elif len(self.bindings) > 1:
                raise ValueError("conclusive full check requires both crash-boundary hypotheses")
            _validate_conclusive_verdict(self.verdict, self.attempts)
        elif self.verdict is CrashVerdict.UNSUPPORTED_TARGET and (
            self.execution_status is not ExecutionStatus.UNSUPPORTED
            or any(
                attempt.execution_status is not ExecutionStatus.UNSUPPORTED
                or attempt.observation is not CrashObservation.NOT_OBSERVED
                for attempt in self.attempts
            )
        ):
            raise ValueError("unsupported verdict contradicts its attempts")
        return self


def _validate_hypothesis_receipt_links(
    receipts: tuple[HypothesisReceipt, ...],
    binding_by_digest: dict[str, AnchorBinding],
    proof_attempts: tuple[AttemptReceipt, ...],
) -> None:
    if len(receipts) != 2 or tuple(receipt.canonical_rank for receipt in receipts) != (1, 2):
        raise ValueError("conclusive verdict requires both canonical crash-boundary hypotheses")
    base_binding_digests = {
        attempt.binding_digest for attempt in proof_attempts if attempt.role is WorldRole.BASE
    }
    if len(base_binding_digests) != 1:
        raise ValueError("hypothesis receipts require one exact BASE binding")
    base_binding = binding_by_digest[next(iter(base_binding_digests))]
    if any(
        receipt.contract_digest != base_binding.contract_digest
        or receipt.originating_base_tree_digest != base_binding.tree_digest
        for receipt in receipts
    ):
        raise ValueError("hypothesis receipts differ from the BASE binding")
    identity_groups = (
        [receipt.hypothesis_id for receipt in receipts],
        [receipt.provisional_capsule_digest for receipt in receipts],
        [receipt.attempt.digest for receipt in receipts],
        [receipt.attempt.receipt_id for receipt in receipts],
        [receipt.attempt.database_id for receipt in receipts],
        [receipt.attempt.execution_nonce for receipt in receipts],
        [spawn.worker_nonce for receipt in receipts for spawn in receipt.attempt.spawns],
        [spawn.ipc_session_id for receipt in receipts for spawn in receipt.attempt.spawns],
    )
    if any(len(values) != len(set(values)) for values in identity_groups):
        raise ValueError("hypothesis receipts require unique hunt identities")
    hunt_freshness = (
        {receipt.attempt.database_id for receipt in receipts},
        {receipt.attempt.execution_nonce for receipt in receipts},
        {spawn.worker_nonce for receipt in receipts for spawn in receipt.attempt.spawns},
        {spawn.ipc_session_id for receipt in receipts for spawn in receipt.attempt.spawns},
    )
    proof_freshness = (
        {attempt.database_id for attempt in proof_attempts},
        {attempt.execution_nonce for attempt in proof_attempts},
        {spawn.worker_nonce for attempt in proof_attempts for spawn in attempt.spawns},
        {spawn.ipc_session_id for attempt in proof_attempts for spawn in attempt.spawns},
    )
    if any(hunt & proof for hunt, proof in zip(hunt_freshness, proof_freshness, strict=True)):
        raise ValueError("hypothesis and proof attempts must have disjoint identities")


def _validate_conclusive_hypothesis_receipts(
    receipts: tuple[HypothesisReceipt, ...],
) -> None:
    if any(
        receipt.attempt.execution_status is not ExecutionStatus.COMPLETED
        or receipt.attempt.integrity_status is not IntegrityStatus.VALID
        for receipt in receipts
    ):
        raise ValueError("conclusive verdict requires completed valid hypothesis attempts")
    selected = [receipt for receipt in receipts if receipt.selected]
    if len(selected) != 1 or not selected[0].reproduced:
        raise ValueError("conclusive verdict requires one selected reproducing hypothesis")
    expected = min(
        receipts,
        key=lambda receipt: (
            not receipt.reproduced,
            receipt.trusted_operation_count,
            receipt.canonical_rank,
            receipt.digest,
        ),
    )
    if selected[0] is not expected:
        raise ValueError("selected hypothesis contradicts deterministic ordering")


def _snapshot_state(snapshot: CreditSnapshot) -> tuple[int, int, int, int]:
    return (
        snapshot.account_balance_cents,
        snapshot.event_ledger_count,
        snapshot.event_ledger_total_cents,
        snapshot.event_marker_count,
    )


def _validate_conclusive_verdict(
    verdict: CrashVerdict, attempts: tuple[AttemptReceipt, ...]
) -> None:
    role_attempts = {
        role: tuple(attempt for attempt in attempts if attempt.role is role)
        for role in WorldRole
        if any(attempt.role is role for attempt in attempts)
    }
    if any(len(receipts) != REQUIRED_CONFIRMATIONS for receipts in role_attempts.values()):
        raise ValueError(
            f"conclusive verdict requires {REQUIRED_CONFIRMATIONS} attempts per claimed role"
        )
    freshness_values = (
        [attempt.database_id for attempt in attempts],
        [attempt.execution_nonce for attempt in attempts],
        [spawn.worker_nonce for attempt in attempts for spawn in attempt.spawns],
        [spawn.ipc_session_id for attempt in attempts for spawn in attempt.spawns],
    )
    if any(len(values) != len(set(values)) for values in freshness_values):
        raise ValueError(
            "conclusive verdict requires globally unique attempt and worker identities"
        )
    observations = {
        role: {attempt.observation for attempt in attempts if attempt.role is role}
        for role in WorldRole
        if any(attempt.role is role for attempt in attempts)
    }
    roles = set(observations)
    duplicate = {CrashObservation.DUPLICATE_EFFECT}
    exactly_once = {CrashObservation.EXACTLY_ONCE}
    if verdict is CrashVerdict.BUG_REPRODUCED:
        coherent = roles == {WorldRole.BASE} and observations[WorldRole.BASE] == duplicate
    elif verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES:
        coherent = (
            roles in ({WorldRole.CANDIDATE}, {WorldRole.CORRECTED})
            and next(iter(observations.values())) == duplicate
        ) or (
            roles
            in (
                {WorldRole.BASE, WorldRole.CANDIDATE},
                {WorldRole.BASE, WorldRole.CANDIDATE, WorldRole.CORRECTED},
            )
            and observations[WorldRole.BASE] == duplicate
            and observations[WorldRole.CANDIDATE] == duplicate
            and (
                WorldRole.CORRECTED not in roles
                or observations[WorldRole.CORRECTED] == exactly_once
            )
        )
    else:
        coherent = (
            roles in ({WorldRole.CANDIDATE}, {WorldRole.CORRECTED})
            and next(iter(observations.values())) == exactly_once
        ) or (
            roles
            in (
                {WorldRole.BASE, WorldRole.CANDIDATE},
                {WorldRole.BASE, WorldRole.CANDIDATE, WorldRole.CORRECTED},
            )
            and observations[WorldRole.BASE] == duplicate
            and observations[WorldRole.CANDIDATE] == exactly_once
            and (
                WorldRole.CORRECTED not in roles
                or observations[WorldRole.CORRECTED] == exactly_once
            )
        )
    if not coherent:
        raise ValueError("verdict contradicts role-specific attempt observations")


__all__ = [
    "AnchorBinding",
    "AttemptReceipt",
    "CrashCheckResult",
    "CrashObservation",
    "CrashVerdict",
    "ExecutionStatus",
    "FaultBoundary",
    "HypothesisReceipt",
    "IntegrityStatus",
    "REQUIRED_CONFIRMATIONS",
    "ReproCapsule",
    "RetryContract",
    "WorldRole",
]
