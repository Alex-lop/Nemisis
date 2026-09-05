"""Strict evidence contracts for the CrashCheck SQLite vertical slice."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from nemisis.hashing import canonical_json, sha256_json
from nemisis.models import ModelCallReceipt, SafeId, Sha256, StrictModel, TruthLabel
from nemisis.safety import safe_relative_path

REQUIRED_CONFIRMATIONS = 5
MAX_SWEEP_COMMITS = 16


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
    PATCH_FAILED_INVARIANT_BROKEN = "PATCH_FAILED_INVARIANT_BROKEN"
    FIX_PROVEN_FOR_THIS_CAPSULE = "FIX_PROVEN_FOR_THIS_CAPSULE"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    UNSUPPORTED_TARGET = "UNSUPPORTED_TARGET"


CONCLUSIVE_VERDICTS = frozenset(
    {
        CrashVerdict.BUG_REPRODUCED,
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES,
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN,
        CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE,
    }
)


class FaultBoundary(StrEnum):
    EFFECT_COMMIT = "effect-commit"
    MARKER_COMMIT = "marker-commit"


class AnchorResolutionStatus(StrEnum):
    ZERO_MATCHES = "ZERO_MATCHES"
    MULTIPLE_MATCHES = "MULTIPLE_MATCHES"
    INVALID_MATCH = "INVALID_MATCH"


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


class ContractProposal(_DigestedModel):
    """Candidate-blind Nemotron proposal receipt: provenance for a drafted contract, never evidence.

    The model saw only the issue text and the base handler. Deterministic code decided whether
    its catalog selection and expected single effect match the audited scenario. A rejected
    proposal drafts no contract; an accepted one changes nothing about how ``check`` decides.
    """

    schema_version: Literal["nemisis.contract-proposal.v1"] = "nemisis.contract-proposal.v1"
    scenario_id: SafeId
    target: str = Field(
        min_length=3,
        max_length=240,
        pattern=r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$",
    )
    issue_digest: Sha256
    base_ref: str = Field(min_length=1, max_length=500)
    base_tree_digest: Sha256
    handler_path: str = Field(min_length=4, max_length=240, pattern=r"^[A-Za-z0-9_./-]+\.py$")
    offered_catalog_ids: tuple[SafeId, ...] = Field(min_length=1, max_length=16)
    required_catalog_id: SafeId
    proposed_catalog_ids: tuple[SafeId, ...] = Field(min_length=1, max_length=16)
    audited_amount_cents: int = Field(gt=0, le=1_000_000)
    proposed_amount_cents: int = Field(ge=-1_000_000_000, le=1_000_000_000)
    accepted: bool
    model_call: ModelCallReceipt

    @model_validator(mode="after")
    def proposal_is_coherent(self) -> ContractProposal:
        safe_relative_path(self.handler_path)
        offered = set(self.offered_catalog_ids)
        if len(offered) != len(self.offered_catalog_ids):
            raise ValueError("offered catalog IDs must be unique")
        if self.required_catalog_id not in offered:
            raise ValueError("required catalog ID was not offered to the model")
        if not set(self.proposed_catalog_ids) <= offered:
            raise ValueError("proposal selected a catalog ID that was not offered")
        if self.model_call.truth_label not in {TruthLabel.LIVE, TruthLabel.MOCKED}:
            raise ValueError("proposal receipt must come from a live or injected model client")
        if not self.model_call.schema_valid or self.model_call.outcome != "success":
            raise ValueError("proposal receipt must record a schema-valid successful call")
        expected = (
            self.required_catalog_id in self.proposed_catalog_ids
            and self.proposed_amount_cents == self.audited_amount_cents
        )
        if self.accepted is not expected:
            raise ValueError("proposal acceptance contradicts its proposed values")
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


class AnchorResolutionReceipt(_DigestedModel):
    """Fail-closed evidence for a supported target that did not map uniquely."""

    schema_version: Literal["1"] = "1"
    role: WorldRole
    transport: TruthLabel
    status: AnchorResolutionStatus
    capsule_digest: Sha256
    contract_digest: Sha256
    scenario_id: SafeId
    source_ref: str = Field(min_length=1, max_length=500)
    resolved_source_identity: str = Field(min_length=1, max_length=500)
    tree_digest: Sha256
    target: str = Field(
        min_length=3,
        max_length=240,
        pattern=r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$",
    )
    matched_paths: tuple[str, ...] = Field(max_length=8)
    detail: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def resolution_is_coherent(self) -> AnchorResolutionReceipt:
        for path in self.matched_paths:
            safe_relative_path(path)
        count = len(self.matched_paths)
        if (
            (self.status is AnchorResolutionStatus.ZERO_MATCHES and count != 0)
            or (self.status is AnchorResolutionStatus.MULTIPLE_MATCHES and count < 2)
            or (self.status is AnchorResolutionStatus.INVALID_MATCH and count != 1)
        ):
            raise ValueError("anchor resolution status contradicts its matched paths")
        return self


class CreditSnapshot(_DigestedModel):
    account_balance_cents: int
    event_ledger_count: int = Field(ge=0)
    event_ledger_total_cents: int
    event_marker_count: int = Field(ge=0, le=1)


def classify_final(snapshot: CreditSnapshot, amount_cents: int) -> CrashObservation:
    """The only rule that turns a final durable state into an observation."""
    state = _snapshot_state(snapshot)
    if state[:3] == (amount_cents * 2, 2, amount_cents * 2):
        return CrashObservation.DUPLICATE_EFFECT
    if state == (amount_cents, 1, amount_cents, 1):
        return CrashObservation.EXACTLY_ONCE
    return CrashObservation.INVARIANT_FAILED


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
    amount_cents: int = Field(gt=0, le=1_000_000)
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
    kill_after_commit: int | None = Field(default=None, ge=1, le=MAX_SWEEP_COMMITS)
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
            # The checkpoint is whatever the handler had committed when it was killed; only the
            # final state decides, through the one shared rule.
            if self.observation is not classify_final(final, self.amount_cents):
                raise ValueError("completed attempt observation contradicts its final state")
        elif self.failure_detail is None:
            raise ValueError("incomplete attempt requires a failure detail")
        return self


class NoFaultReplayReceipt(_DigestedModel):
    """One fresh two-process delivery with no kill: the handler's commit schedule, observed.

    On the base it is the no-crash control (the duplicate needs the crash). On a candidate or
    corrected tree it is the census that tells the commit sweep how many kill points exist and
    which store operation each one is.
    """

    schema_version: Literal["2"] = "2"
    receipt_id: SafeId
    role: WorldRole = WorldRole.BASE
    transport: Literal[TruthLabel.LOCAL] = TruthLabel.LOCAL
    execution_status: ExecutionStatus
    integrity_status: IntegrityStatus
    observation: CrashObservation
    parent_capsule_digest: Sha256
    contract_digest: Sha256
    binding_digest: Sha256
    tree_digest: Sha256
    post_execution_tree_digest: Sha256 | None = None
    environment_digest: Sha256
    event_digest: Sha256
    amount_cents: int = Field(gt=0, le=1_000_000)
    initial_database_digest: Sha256
    initial_database_file_digest: Sha256 | None = None
    database_id: SafeId
    execution_nonce: SafeId
    started_at: datetime
    ended_at: datetime
    spawns: tuple[WorkerSpawnReceipt, ...] = Field(max_length=2)
    first_delivery_operations: tuple[SafeId, ...] = Field(default=(), max_length=MAX_SWEEP_COMMITS)
    replay_operations: tuple[SafeId, ...] = Field(default=(), max_length=MAX_SWEEP_COMMITS)
    initial_snapshot: CreditSnapshot | None = None
    first_delivery_snapshot: CreditSnapshot | None = None
    final_snapshot: CreditSnapshot | None = None
    failure_detail: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def evidence_is_coherent(self) -> NoFaultReplayReceipt:
        if self.ended_at < self.started_at:
            raise ValueError("no-fault replay ended before it started")
        if len({spawn.spawn_index for spawn in self.spawns}) != len(self.spawns):
            raise ValueError("no-fault worker spawn indices must be unique")
        if any(spawn.event_digest != self.event_digest for spawn in self.spawns):
            raise ValueError("no-fault worker event digest differs from the replay")
        for snapshot in (
            self.initial_snapshot,
            self.first_delivery_snapshot,
            self.final_snapshot,
        ):
            if snapshot is not None:
                snapshot._require_canonical_digest()
        if self.execution_status is ExecutionStatus.COMPLETED:
            if (
                self.integrity_status is not IntegrityStatus.VALID
                or self.failure_detail is not None
                or self.post_execution_tree_digest != self.tree_digest
                or len(self.spawns) != 2
                or tuple(spawn.phase for spawn in self.spawns) != ("first", "replay")
                or any(spawn.exit_code != 0 for spawn in self.spawns)
                or len({spawn.worker_nonce for spawn in self.spawns}) != 2
                or len({spawn.ipc_session_id for spawn in self.spawns}) != 2
                or self.initial_database_file_digest is None
                or self.initial_snapshot is None
                or self.first_delivery_snapshot is None
                or self.final_snapshot is None
            ):
                raise ValueError("completed no-fault replay lacks exact two-process evidence")
            if _snapshot_state(self.initial_snapshot) != (0, 0, 0, 0):
                raise ValueError("no-fault replay did not begin from the seeded state")
            if self.observation is not classify_final(self.final_snapshot, self.amount_cents):
                raise ValueError("no-fault replay observation contradicts its final state")
            if not self.first_delivery_operations:
                raise ValueError("completed no-fault replay recorded no store commits")
        elif self.failure_detail is None:
            raise ValueError("incomplete no-fault replay requires a failure detail")
        return self


class CommitSweepReceipt(_DigestedModel):
    """Kill after every store commit the handler makes, not only at the base's boundary.

    The capsule's boundary proves the patch beat the crash the base had. The sweep proves it did
    not trade that crash for another one: a handler that marks first and credits second passes the
    boundary and loses the credit when killed between the two. ``FIX_PROVEN_FOR_THIS_CAPSULE``
    requires every kill point in the sweep to end exactly once.
    """

    schema_version: Literal["1"] = "1"
    role: WorldRole
    capsule_digest: Sha256
    binding_digest: Sha256
    census: NoFaultReplayReceipt
    attempts: tuple[AttemptReceipt, ...] = Field(default=(), max_length=MAX_SWEEP_COMMITS)
    observation: CrashObservation

    @model_validator(mode="after")
    def sweep_is_coherent(self) -> CommitSweepReceipt:
        if self.role is WorldRole.BASE:
            raise ValueError("the commit sweep applies to claimed fixes, not the base")
        self.census._require_canonical_digest()
        for attempt in self.attempts:
            attempt._require_canonical_digest()
        if self.census.role is not self.role or self.census.binding_digest != self.binding_digest:
            raise ValueError("sweep census differs from the sweep role or binding")
        if any(
            attempt.role is not self.role
            or attempt.binding_digest != self.binding_digest
            or attempt.capsule_digest != self.capsule_digest
            for attempt in self.attempts
        ):
            raise ValueError("sweep attempt differs from the sweep role, binding, or capsule")
        census_complete = (
            self.census.execution_status is ExecutionStatus.COMPLETED
            and self.census.integrity_status is IntegrityStatus.VALID
        )
        expected_kill_points = (
            tuple(range(1, len(self.census.first_delivery_operations) + 1))
            if census_complete
            else ()
        )
        if tuple(attempt.kill_after_commit for attempt in self.attempts) != expected_kill_points:
            raise ValueError("sweep must kill once after each commit the census observed")
        identities = (
            [attempt.receipt_id for attempt in self.attempts] + [self.census.receipt_id],
            [attempt.database_id for attempt in self.attempts] + [self.census.database_id],
            [attempt.execution_nonce for attempt in self.attempts] + [self.census.execution_nonce],
        )
        if any(len(values) != len(set(values)) for values in identities):
            raise ValueError("sweep worlds require fresh identities")
        if self.observation is not sweep_observation(self.census, self.attempts):
            raise ValueError("sweep observation contradicts its attempts")
        return self


def sweep_observation(
    census: NoFaultReplayReceipt, attempts: tuple[AttemptReceipt, ...]
) -> CrashObservation:
    """Exactly once only if the census and every kill point say so; the worst failure otherwise."""
    completed = (
        census.execution_status is ExecutionStatus.COMPLETED
        and census.integrity_status is IntegrityStatus.VALID
        and bool(attempts)
        and all(
            attempt.execution_status is ExecutionStatus.COMPLETED
            and attempt.integrity_status is IntegrityStatus.VALID
            for attempt in attempts
        )
    )
    observations = {census.observation, *(attempt.observation for attempt in attempts)}
    if CrashObservation.DUPLICATE_EFFECT in observations:
        return CrashObservation.DUPLICATE_EFFECT
    if CrashObservation.INVARIANT_FAILED in observations:
        return CrashObservation.INVARIANT_FAILED
    if completed and observations == {CrashObservation.EXACTLY_ONCE}:
        return CrashObservation.EXACTLY_ONCE
    return CrashObservation.NOT_OBSERVED


class MinimizationReceipt(_DigestedModel):
    """Fixture-scoped deletion check for the selected schedule's sole fault action."""

    schema_version: Literal["2"] = "2"
    parent_capsule_digest: Sha256
    contract_digest: Sha256
    originating_base_tree_digest: Sha256
    parent_schedule: tuple[FaultBoundary, ...] = Field(min_length=1, max_length=1)
    candidate_schedule: tuple[FaultBoundary, ...] = Field(max_length=1)
    removed_fault: FaultBoundary
    confirmations: tuple[NoFaultReplayReceipt, ...] = Field(min_length=2, max_length=2)
    empty_schedule_reproduced_duplicate: bool
    deletion_accepted: bool
    sole_fault_action_necessary_for_fixture: bool
    trace_digest: Sha256

    @model_validator(mode="after")
    def reduction_is_coherent(self) -> MinimizationReceipt:
        expected_parent = (FaultBoundary.EFFECT_COMMIT,)
        if (
            self.parent_schedule != expected_parent
            or self.candidate_schedule
            or self.removed_fault is not FaultBoundary.EFFECT_COMMIT
        ):
            raise ValueError("deletion trial differs from the trusted one-fault schedule")
        for attempt in self.confirmations:
            attempt._require_canonical_digest()
        if any(
            attempt.role is not WorldRole.BASE
            or attempt.parent_capsule_digest != self.parent_capsule_digest
            or attempt.contract_digest != self.contract_digest
            or attempt.tree_digest != self.originating_base_tree_digest
            for attempt in self.confirmations
        ):
            raise ValueError("deletion confirmations differ from their exact parent inputs")
        unique_groups = (
            [attempt.digest for attempt in self.confirmations],
            [attempt.receipt_id for attempt in self.confirmations],
            [attempt.database_id for attempt in self.confirmations],
            [attempt.execution_nonce for attempt in self.confirmations],
            [spawn.worker_nonce for attempt in self.confirmations for spawn in attempt.spawns],
            [spawn.ipc_session_id for attempt in self.confirmations for spawn in attempt.spawns],
        )
        shared_groups = (
            [attempt.binding_digest for attempt in self.confirmations],
            [attempt.environment_digest for attempt in self.confirmations],
            [attempt.event_digest for attempt in self.confirmations],
            [attempt.initial_database_digest for attempt in self.confirmations],
        )
        database_file_digests = {
            attempt.initial_database_file_digest
            for attempt in self.confirmations
            if attempt.initial_database_file_digest is not None
        }
        if (
            any(len(values) != len(set(values)) for values in unique_groups)
            or any(len(set(values)) != 1 for values in shared_groups)
            or len(database_file_digests) > 1
        ):
            raise ValueError("deletion confirmations require fresh execution identities")
        completed = all(
            attempt.execution_status is ExecutionStatus.COMPLETED
            and attempt.integrity_status is IntegrityStatus.VALID
            for attempt in self.confirmations
        )
        reproduced = completed and all(
            attempt.observation is CrashObservation.DUPLICATE_EFFECT
            for attempt in self.confirmations
        )
        necessary = completed and all(
            attempt.observation is CrashObservation.EXACTLY_ONCE for attempt in self.confirmations
        )
        if (
            self.empty_schedule_reproduced_duplicate is not reproduced
            or self.deletion_accepted is not reproduced
            or self.sole_fault_action_necessary_for_fixture is not necessary
        ):
            raise ValueError("deletion decision contradicts its confirmation receipts")
        stable = {
            "candidate_schedule": self.candidate_schedule,
            "confirmation_count": len(self.confirmations),
            "contract_digest": self.contract_digest,
            "sole_fault_action_necessary_for_fixture": (
                self.sole_fault_action_necessary_for_fixture
            ),
            "originating_base_tree_digest": self.originating_base_tree_digest,
            "parent_capsule_digest": self.parent_capsule_digest,
            "parent_schedule": self.parent_schedule,
            "removed_fault": self.removed_fault,
            "empty_schedule_reproduced_duplicate": self.empty_schedule_reproduced_duplicate,
            "deletion_accepted": self.deletion_accepted,
        }
        if sha256_json(stable) != self.trace_digest:
            raise ValueError("one-action deletion trace digest mismatch")
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
    anchor_resolutions: tuple[AnchorResolutionReceipt, ...] = Field(default=(), max_length=1)
    hypothesis_receipts: tuple[HypothesisReceipt, ...] = Field(default=(), max_length=2)
    minimization_receipts: tuple[MinimizationReceipt, ...] = Field(default=(), max_length=1)
    bindings: tuple[AnchorBinding, ...] = Field(default=(), max_length=3)
    attempts: tuple[AttemptReceipt, ...] = Field(default=(), max_length=24)
    sweeps: tuple[CommitSweepReceipt, ...] = Field(default=(), max_length=2)
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
        for hypothesis in self.hypothesis_receipts:
            hypothesis._require_canonical_digest()
        for reduction in self.minimization_receipts:
            reduction._require_canonical_digest()
        for anchor_resolution in self.anchor_resolutions:
            anchor_resolution._require_canonical_digest()
        for sweep in self.sweeps:
            sweep._require_canonical_digest()
        for artifact_path in self.artifacts.values():
            safe_relative_path(artifact_path)
        _validate_anchor_resolution_context(self)
        if not self.attempts:
            if self.sweeps:
                raise ValueError("a commit sweep requires boundary attempts")
            return self
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
        _validate_sweeps(self)
        if self.hypothesis_receipts:
            _validate_hypothesis_receipt_links(
                self.hypothesis_receipts, binding_by_digest, self.attempts
            )
        if self.minimization_receipts:
            _validate_minimization_receipts(
                self.hypothesis_receipts,
                self.minimization_receipts,
                binding_by_digest,
                self.attempts,
            )
        completed = all(
            attempt.execution_status is ExecutionStatus.COMPLETED for attempt in self.attempts
        )
        execution_matches = (
            self.execution_status is ExecutionStatus.SETUP_ERROR
            if self.anchor_resolutions
            else (self.execution_status is ExecutionStatus.COMPLETED) is completed
            and (
                completed
                or self.execution_status in {attempt.execution_status for attempt in self.attempts}
            )
        )
        if not execution_matches:
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
        if self.anchor_resolutions:
            expected_integrity = IntegrityStatus.INCOMPLETE
        if self.integrity_status is not expected_integrity:
            raise ValueError("result integrity status contradicts its attempts")
        if self.verdict in CONCLUSIVE_VERDICTS:
            if not completed or expected_integrity is not IntegrityStatus.VALID:
                raise ValueError("conclusive verdict requires completed valid attempts")
            if self.hypothesis_receipts:
                _validate_conclusive_hypothesis_receipts(self.hypothesis_receipts)
                if (
                    len(self.minimization_receipts) != 1
                    or not self.minimization_receipts[0].sole_fault_action_necessary_for_fixture
                ):
                    raise ValueError(
                        "conclusive full check requires a fixture-scoped one-action deletion proof"
                    )
            elif len(self.bindings) > 1:
                raise ValueError("conclusive full check requires both crash-boundary hypotheses")
            _validate_conclusive_verdict(self.verdict, self.attempts, self.sweeps)
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


def _validate_anchor_resolution_context(result: CrashCheckResult) -> None:
    resolution = result.anchor_resolutions[0] if result.anchor_resolutions else None
    if resolution is not None and (
        resolution.capsule_digest != result.capsule_digest
        or resolution.transport is not result.transport
    ):
        raise ValueError("anchor resolution differs from the result capsule or transport")
    if not result.attempts:
        if (
            result.bindings
            or resolution is None
            or result.hypothesis_receipts
            or result.minimization_receipts
            or result.verdict is not CrashVerdict.EVIDENCE_INCOMPLETE
            or result.execution_status is not ExecutionStatus.SETUP_ERROR
            or result.integrity_status is not IntegrityStatus.INCOMPLETE
        ):
            raise ValueError("attempt-free result requires one failed anchor resolution")
        return
    if resolution is None:
        return
    prior_roles = {attempt.role for attempt in result.attempts}
    expected_roles = {
        WorldRole.BASE: set(),
        WorldRole.CANDIDATE: {WorldRole.BASE},
        WorldRole.CORRECTED: {WorldRole.BASE, WorldRole.CANDIDATE},
    }[resolution.role]
    if (
        result.verdict is not CrashVerdict.EVIDENCE_INCOMPLETE
        or result.execution_status is not ExecutionStatus.SETUP_ERROR
        or result.integrity_status is not IntegrityStatus.INCOMPLETE
        or prior_roles != expected_roles
        or len(result.hypothesis_receipts) != 2
        or len(result.minimization_receipts) != 1
        or any(
            sum(attempt.role is role for attempt in result.attempts) != REQUIRED_CONFIRMATIONS
            for role in expected_roles
        )
        or any(
            attempt.execution_status is not ExecutionStatus.COMPLETED
            or attempt.integrity_status is not IntegrityStatus.VALID
            for attempt in result.attempts
        )
    ):
        raise ValueError("failed anchor resolution requires exact valid prior-role evidence")


def _validate_minimization_receipts(
    hypothesis_receipts: tuple[HypothesisReceipt, ...],
    minimization_receipts: tuple[MinimizationReceipt, ...],
    binding_by_digest: dict[str, AnchorBinding],
    proof_attempts: tuple[AttemptReceipt, ...],
) -> None:
    if len(minimization_receipts) != 1 or len(hypothesis_receipts) != 2:
        raise ValueError("minimization requires one trial after the canonical hypothesis hunt")
    receipt = minimization_receipts[0]
    selected = [item for item in hypothesis_receipts if item.selected]
    base_bindings = {
        attempt.binding_digest for attempt in proof_attempts if attempt.role is WorldRole.BASE
    }
    if len(selected) != 1 or len(base_bindings) != 1:
        raise ValueError("minimization requires one selected witness and one base binding")
    base_binding = binding_by_digest[next(iter(base_bindings))]
    selected_attempt = selected[0].attempt
    if (
        receipt.parent_capsule_digest != selected[0].provisional_capsule_digest
        or receipt.contract_digest != base_binding.contract_digest
        or receipt.originating_base_tree_digest != base_binding.tree_digest
        or any(
            attempt.binding_digest != base_binding.digest
            or attempt.environment_digest != selected_attempt.environment_digest
            or attempt.event_digest != selected_attempt.event_digest
            or attempt.initial_database_digest != selected_attempt.initial_database_digest
            or (
                attempt.initial_database_file_digest is not None
                and attempt.initial_database_file_digest
                != selected_attempt.initial_database_file_digest
            )
            for attempt in receipt.confirmations
        )
    ):
        raise ValueError("minimization receipt differs from the selected base witness")
    minimization_freshness = (
        {attempt.digest for attempt in receipt.confirmations},
        {attempt.receipt_id for attempt in receipt.confirmations},
        {attempt.database_id for attempt in receipt.confirmations},
        {attempt.execution_nonce for attempt in receipt.confirmations},
        {spawn.worker_nonce for attempt in receipt.confirmations for spawn in attempt.spawns},
        {spawn.ipc_session_id for attempt in receipt.confirmations for spawn in attempt.spawns},
    )
    other_attempts = (
        *(item.attempt for item in hypothesis_receipts),
        *proof_attempts,
    )
    other_freshness = (
        {attempt.digest for attempt in other_attempts},
        {attempt.receipt_id for attempt in other_attempts},
        {attempt.database_id for attempt in other_attempts},
        {attempt.execution_nonce for attempt in other_attempts},
        {spawn.worker_nonce for attempt in other_attempts for spawn in attempt.spawns},
        {spawn.ipc_session_id for attempt in other_attempts for spawn in attempt.spawns},
    )
    if any(
        minimized & other
        for minimized, other in zip(minimization_freshness, other_freshness, strict=True)
    ):
        raise ValueError("minimization, hunt, and proof identities must be disjoint")


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


def _validate_sweeps(result: CrashCheckResult) -> None:
    binding_by_digest = {binding.digest: binding for binding in result.bindings}
    roles = [sweep.role for sweep in result.sweeps]
    if len(roles) != len(set(roles)):
        raise ValueError("each role may carry at most one commit sweep")
    boundary_identities = (
        {attempt.database_id for attempt in result.attempts},
        {attempt.execution_nonce for attempt in result.attempts},
    )
    for sweep in result.sweeps:
        role_bindings = {
            attempt.binding_digest for attempt in result.attempts if attempt.role is sweep.role
        }
        if role_bindings != {sweep.binding_digest} or sweep.binding_digest not in binding_by_digest:
            raise ValueError("commit sweep is not bound to its role's anchor binding")
        if sweep.capsule_digest != result.capsule_digest:
            raise ValueError("commit sweep uses a different capsule")
        if any(attempt.transport is not result.transport for attempt in sweep.attempts):
            raise ValueError("sweep attempt transport differs from result transport")
        sweep_identities = (
            {attempt.database_id for attempt in sweep.attempts} | {sweep.census.database_id},
            {attempt.execution_nonce for attempt in sweep.attempts}
            | {sweep.census.execution_nonce},
        )
        if any(a & b for a, b in zip(sweep_identities, boundary_identities, strict=True)):
            raise ValueError("sweep and boundary worlds must have disjoint identities")


def effective_observation(
    role: WorldRole,
    attempts: tuple[AttemptReceipt, ...],
    sweeps: tuple[CommitSweepReceipt, ...],
) -> CrashObservation | None:
    """The boundary worlds decide unless they are exactly once; then the sweep must agree."""
    observations = {attempt.observation for attempt in attempts if attempt.role is role}
    if len(observations) != 1:
        return None
    boundary = next(iter(observations))
    if role is WorldRole.BASE or boundary is not CrashObservation.EXACTLY_ONCE:
        return boundary
    sweep = next((item for item in sweeps if item.role is role), None)
    if sweep is None:
        return CrashObservation.NOT_OBSERVED
    return sweep.observation


def _validate_conclusive_verdict(
    verdict: CrashVerdict,
    attempts: tuple[AttemptReceipt, ...],
    sweeps: tuple[CommitSweepReceipt, ...] = (),
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
        role: {effective_observation(role, attempts, sweeps)}
        for role in WorldRole
        if any(attempt.role is role for attempt in attempts)
    }
    roles = set(observations)
    duplicate = {CrashObservation.DUPLICATE_EFFECT}
    exactly_once = {CrashObservation.EXACTLY_ONCE}
    invariant_failed = {CrashObservation.INVARIANT_FAILED}
    if verdict is CrashVerdict.BUG_REPRODUCED:
        coherent = roles == {WorldRole.BASE} and observations[WorldRole.BASE] == duplicate
    elif verdict in {
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES,
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN,
    }:
        failed = (
            duplicate if verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES else invariant_failed
        )
        coherent = (
            roles in ({WorldRole.CANDIDATE}, {WorldRole.CORRECTED})
            and next(iter(observations.values())) == failed
        ) or (
            roles
            in (
                {WorldRole.BASE, WorldRole.CANDIDATE},
                {WorldRole.BASE, WorldRole.CANDIDATE, WorldRole.CORRECTED},
            )
            and observations[WorldRole.BASE] == duplicate
            and observations[WorldRole.CANDIDATE] == failed
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
    "CONCLUSIVE_VERDICTS",
    "MAX_SWEEP_COMMITS",
    "AnchorBinding",
    "CommitSweepReceipt",
    "AnchorResolutionReceipt",
    "AnchorResolutionStatus",
    "AttemptReceipt",
    "ContractProposal",
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
    "classify_final",
    "effective_observation",
    "sweep_observation",
]
