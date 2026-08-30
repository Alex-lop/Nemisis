"""Versioned local benchmark for the audited CrashCheck hero fixture."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import runpy
import sqlite3
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from time import monotonic_ns
from typing import Literal, Self, cast
from xml.etree import ElementTree

from pydantic import Field, model_validator

from nemisis.crash_fixture import (
    ATOMIC_REF,
    BUGGY_REF,
    EVENT_DIGEST,
    FIXTURE_REFS,
    MISLEADING_GREEN_REF,
    SCENARIO_ID,
    FixtureEvent,
    FixtureVariant,
    load_event,
    materialize_fixture,
)
from nemisis.crash_models import (
    AttemptReceipt,
    CrashCheckResult,
    CrashObservation,
    CrashVerdict,
    ExecutionStatus,
    FaultBoundary,
    IntegrityStatus,
    ReproCapsule,
    WorldRole,
)
from nemisis.crashcheck import CONFIRMATIONS, _write_exact, check
from nemisis.hashing import canonical_json, sha256_json, sha256_tree
from nemisis.local import _run_process, source_commit
from nemisis.models import Sha256, StrictModel, TruthLabel
from nemisis.sqlite_credit import runner_environment_digest

SCHEMA_VERSION: Literal["nemisis.crashcheck.benchmark.v1"] = "nemisis.crashcheck.benchmark.v1"
PYTEST_TIMEOUT_SECONDS = 30
MAX_JUNIT_BYTES = 512_000

_EXPECTED_OBSERVATIONS = {
    BUGGY_REF: CrashObservation.DUPLICATE_EFFECT,
    MISLEADING_GREEN_REF: CrashObservation.DUPLICATE_EFFECT,
    ATOMIC_REF: CrashObservation.EXACTLY_ONCE,
}
_EXPECTED_ROLES = {
    BUGGY_REF: WorldRole.BASE,
    MISLEADING_GREEN_REF: WorldRole.CANDIDATE,
    ATOMIC_REF: WorldRole.CORRECTED,
}


class BenchmarkError(RuntimeError):
    """The benchmark could not produce complete, trustworthy evidence."""


class CheckOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class StateCounts(StrictModel):
    balance_cents: int
    ledger_count: int = Field(ge=0)
    ledger_total_cents: int
    marker_count: int = Field(ge=0, le=1)


class PytestMeasurement(StrictModel):
    outcome: CheckOutcome
    test_count: int = Field(ge=1)
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    wall_time_ns: int = Field(ge=0)

    @model_validator(mode="after")
    def counts_are_coherent(self) -> Self:
        if (
            self.passed_count + self.failed_count + self.error_count + self.skipped_count
            != self.test_count
        ):
            raise ValueError("pytest counts do not sum to the collected test count")
        expected = CheckOutcome.PASS if self.passed_count == self.test_count else CheckOutcome.FAIL
        if self.outcome is not expected:
            raise ValueError("pytest outcome differs from its counts")
        return self


class SequentialMeasurement(StrictModel):
    outcome: CheckOutcome
    observation: CrashObservation
    delivery_count: Literal[2] = 2
    state: StateCounts
    wall_time_ns: int = Field(ge=0)

    @model_validator(mode="after")
    def outcome_matches_observation(self) -> Self:
        expected = (
            CheckOutcome.PASS
            if self.observation is CrashObservation.EXACTLY_ONCE
            else CheckOutcome.FAIL
        )
        if self.outcome is not expected:
            raise ValueError("sequential outcome differs from its observation")
        return self


class CrashAttemptMeasurement(StrictModel):
    attempt: int = Field(ge=1, le=CONFIRMATIONS)
    execution_status: ExecutionStatus
    integrity_status: IntegrityStatus
    observation: CrashObservation
    duration_ns: int = Field(ge=0)
    final_state: StateCounts


class ObservationCount(StrictModel):
    observation: CrashObservation
    count: int = Field(ge=0, le=CONFIRMATIONS)


class HuntMeasurement(StrictModel):
    role: Literal[WorldRole.BASE] = WorldRole.BASE
    attempted_world_count: Literal[2] = 2
    completed_world_count: Literal[2] = 2
    valid_world_count: Literal[2] = 2
    reproducing_world_count: Literal[1] = 1
    selected_world_count: Literal[1] = 1
    selected_hypothesis_id: Literal["effect-commit-v1"] = "effect-commit-v1"
    selected_fault_boundary: Literal[FaultBoundary.EFFECT_COMMIT] = FaultBoundary.EFFECT_COMMIT
    hypothesis_selection_ratio: float = Field(default=0.5, ge=0.5, le=0.5)
    minimization_trial_count: Literal[1] = 1
    minimization_world_count: Literal[2] = 2
    initial_fault_action_count: Literal[1] = 1
    final_fault_action_count: Literal[1] = 1
    minimization_ratio: float = Field(default=1.0, ge=1.0, le=1.0)
    minimization_wall_time_ns: int = Field(ge=0)
    time_to_first_witness_ns: int = Field(ge=0)
    wall_time_ns: int = Field(ge=0)

    @model_validator(mode="after")
    def timings_are_coherent(self) -> Self:
        if self.time_to_first_witness_ns > self.wall_time_ns:
            raise ValueError("hunt witness time exceeds hunt wall time")
        return self


class CrashMeasurement(StrictModel):
    role: WorldRole
    observation: CrashObservation
    observation_counts: tuple[ObservationCount, ...] = Field(min_length=4, max_length=4)
    attempted_world_count: Literal[5] = 5
    completed_world_count: int = Field(ge=0, le=CONFIRMATIONS)
    valid_world_count: int = Field(ge=0, le=CONFIRMATIONS)
    unique_database_count: int = Field(ge=0, le=CONFIRMATIONS)
    unique_execution_nonce_count: int = Field(ge=0, le=CONFIRMATIONS)
    unique_worker_nonce_count: int = Field(ge=0, le=CONFIRMATIONS * 2)
    unique_ipc_session_count: int = Field(ge=0, le=CONFIRMATIONS * 2)
    time_to_first_witness_ns: int = Field(ge=0)
    wall_time_ns: int = Field(ge=0)
    attempts: tuple[CrashAttemptMeasurement, ...] = Field(
        min_length=CONFIRMATIONS, max_length=CONFIRMATIONS
    )

    @model_validator(mode="after")
    def counts_are_coherent(self) -> Self:
        expected_order = tuple(CrashObservation)
        if tuple(item.observation for item in self.observation_counts) != expected_order:
            raise ValueError("observation counts are not in canonical enum order")
        if sum(item.count for item in self.observation_counts) != self.attempted_world_count:
            raise ValueError("observation counts do not sum to the attempted worlds")
        if tuple(item.attempt for item in self.attempts) != tuple(range(1, CONFIRMATIONS + 1)):
            raise ValueError("attempt measurements are not canonically ordered")
        return self


class BenchmarkCase(StrictModel):
    ref: str = Field(min_length=1, max_length=200)
    variant: Literal["buggy", "misleading-green", "atomic"]
    tree_digest: Sha256
    pytest: PytestMeasurement
    sequential: SequentialMeasurement
    crashcheck: CrashMeasurement


class BenchmarkEnvironment(StrictModel):
    python_implementation: str = Field(min_length=1, max_length=100)
    python_version: str = Field(min_length=1, max_length=100)
    pytest_version: str = Field(min_length=1, max_length=100)
    sqlite_version: str = Field(min_length=1, max_length=100)
    platform_system: str = Field(min_length=1, max_length=100)
    platform_machine: str = Field(min_length=1, max_length=100)
    crashcheck_environment_digest: Sha256


class BenchmarkResult(StrictModel):
    schema_version: Literal["nemisis.crashcheck.benchmark.v1"] = "nemisis.crashcheck.benchmark.v1"
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$", max_length=40)
    scenario_id: Literal["sqlite-credit-v1"] = "sqlite-credit-v1"
    capsule_digest: Sha256
    engine_code_digest: Sha256
    contract_digest: Sha256
    event_digest: Sha256
    input_digest: Sha256
    environment: BenchmarkEnvironment
    hunt: HuntMeasurement
    crashcheck_verdict: CrashVerdict
    crashcheck_wall_time_ns: int = Field(ge=0)
    wall_time_ns: int = Field(ge=0)
    cases: tuple[BenchmarkCase, ...] = Field(min_length=3, max_length=3)
    result_digest: Sha256

    @model_validator(mode="after")
    def benchmark_is_canonical_and_bound(self) -> Self:
        if tuple(case.ref for case in self.cases) != FIXTURE_REFS:
            raise ValueError("benchmark cases are not in canonical fixture order")
        if any(case.crashcheck.role is not _EXPECTED_ROLES[case.ref] for case in self.cases):
            raise ValueError("benchmark case role differs from the audited matrix")
        if any(
            case.pytest.outcome is not CheckOutcome.PASS
            or case.sequential.outcome is not CheckOutcome.PASS
            or case.crashcheck.observation is not _EXPECTED_OBSERVATIONS[case.ref]
            for case in self.cases
        ):
            raise ValueError("benchmark case outcome differs from the audited matrix")
        expected_input_digest = _input_digest(
            self.source_commit,
            self.capsule_digest,
            self.engine_code_digest,
            self.event_digest,
            self.environment,
            self.hunt,
            self.cases,
        )
        if self.input_digest != expected_input_digest:
            raise ValueError("benchmark input digest mismatch")
        payload = self.model_dump(mode="json", exclude={"result_digest"})
        if sha256_json(payload) != self.result_digest:
            raise ValueError("benchmark result digest mismatch")
        return self


class _SequentialStore:
    def __init__(self) -> None:
        self.balance_cents = 0
        self.ledger: list[int] = []
        self.processed_events: set[str] = set()

    def processed(self, event_id: str) -> bool:
        return event_id in self.processed_events

    def credit(self, account_id: str, event_id: str, amount_cents: int) -> None:
        del account_id, event_id
        self.balance_cents += amount_cents
        self.ledger.append(amount_cents)

    def mark_processed(self, event_id: str) -> None:
        self.processed_events.add(event_id)

    def credit_and_mark(self, account_id: str, event_id: str, amount_cents: int) -> None:
        if not self.processed(event_id):
            self.credit(account_id, event_id, amount_cents)
            self.mark_processed(event_id)

    def snapshot(self) -> StateCounts:
        return StateCounts(
            balance_cents=self.balance_cents,
            ledger_count=len(self.ledger),
            ledger_total_cents=sum(self.ledger),
            marker_count=len(self.processed_events),
        )


def run_benchmark(output: Path) -> BenchmarkResult:
    """Run and canonically publish the fixed three-tree local benchmark."""
    started = monotonic_ns()
    commit = source_commit()
    if commit is None or commit.endswith("-dirty"):
        raise BenchmarkError("a clean exact source_commit() value is required")

    with tempfile.TemporaryDirectory(prefix="nemisis-benchmark-") as temporary:
        root = Path(temporary)
        measured: dict[
            str, tuple[FixtureVariant, str, PytestMeasurement, SequentialMeasurement]
        ] = {}
        for ref in FIXTURE_REFS:
            fixture = materialize_fixture(ref, root / "trees" / fixture_name(ref))
            pytest_result = _measure_pytest(fixture.path, root / "pytest" / fixture.variant)
            if sha256_tree(fixture.path) != fixture.tree_digest:
                raise BenchmarkError("the existing pytest suite changed its audited source tree")
            sequential = _measure_sequential(fixture.path)
            if sha256_tree(fixture.path) != fixture.tree_digest:
                raise BenchmarkError("the sequential check changed its audited source tree")
            if (
                pytest_result.outcome is not CheckOutcome.PASS
                or pytest_result.test_count != 1
                or sequential.observation is not CrashObservation.EXACTLY_ONCE
            ):
                raise BenchmarkError("the audited pytest/sequential outcome matrix changed")
            measured[ref] = (
                fixture.variant,
                fixture.tree_digest,
                pytest_result,
                sequential,
            )

        # CrashCheck rejects symlinked evidence parents; resolve macOS's /var -> /private/var.
        artifact_root = (root / "crashcheck-artifacts").resolve()
        previous_artifact_root = os.environ.get("NEMISIS_ARTIFACT_ROOT")
        os.environ["NEMISIS_ARTIFACT_ROOT"] = str(artifact_root)
        crash_started = monotonic_ns()
        try:
            crash_result = check(
                BUGGY_REF,
                MISLEADING_GREEN_REF,
                SCENARIO_ID,
                corrected=ATOMIC_REF,
                mode="local",
            )
        finally:
            crash_wall_time_ns = monotonic_ns() - crash_started
            if previous_artifact_root is None:
                os.environ.pop("NEMISIS_ARTIFACT_ROOT", None)
            else:
                os.environ["NEMISIS_ARTIFACT_ROOT"] = previous_artifact_root

        if crash_result.engine_source_commit != commit:
            raise BenchmarkError("CrashCheck evidence uses a different source_commit() value")

        capsule_path = (artifact_root / crash_result.artifacts.get("capsule", "")).resolve()
        try:
            capsule_path.relative_to(artifact_root)
            capsule = ReproCapsule.model_validate_json(capsule_path.read_bytes())
        except (OSError, ValueError) as error:
            raise BenchmarkError("CrashCheck did not publish a valid frozen capsule") from error
        hunt = _measure_hunt(crash_result, capsule)
        crash_by_ref = _measure_crashcheck(crash_result, capsule, measured)

        cases = tuple(
            BenchmarkCase(
                ref=ref,
                variant=measured[ref][0],
                tree_digest=measured[ref][1],
                pytest=measured[ref][2],
                sequential=measured[ref][3],
                crashcheck=crash_by_ref[ref],
            )
            for ref in FIXTURE_REFS
        )

    environment = BenchmarkEnvironment(
        python_implementation=platform.python_implementation(),
        python_version=platform.python_version(),
        pytest_version=importlib.metadata.version("pytest"),
        sqlite_version=sqlite3.sqlite_version,
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        crashcheck_environment_digest=runner_environment_digest(),
    )
    input_digest = _input_digest(
        commit,
        capsule.digest,
        capsule.engine_code_digest,
        capsule.event_digest,
        environment,
        hunt,
        cases,
    )
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "source_commit": commit,
        "scenario_id": SCENARIO_ID,
        "capsule_digest": capsule.digest,
        "engine_code_digest": capsule.engine_code_digest,
        "contract_digest": capsule.contract_digest,
        "event_digest": capsule.event_digest,
        "input_digest": input_digest,
        "environment": environment,
        "hunt": hunt,
        "crashcheck_verdict": crash_result.verdict,
        "crashcheck_wall_time_ns": crash_wall_time_ns,
        "wall_time_ns": monotonic_ns() - started,
        "cases": cases,
    }
    payload["result_digest"] = sha256_json(payload)
    result = BenchmarkResult.model_validate(payload)
    if source_commit() != commit:
        raise BenchmarkError("source_commit() changed during the benchmark")
    _write_exact(output, canonical_json(result) + b"\n")
    return result


def fixture_name(ref: str) -> str:
    try:
        return {
            BUGGY_REF: "buggy",
            MISLEADING_GREEN_REF: "misleading-green",
            ATOMIC_REF: "atomic",
        }[ref]
    except KeyError:
        raise BenchmarkError(f"unsupported benchmark fixture: {ref}") from None


def _measure_pytest(source: Path, work: Path) -> PytestMeasurement:
    work.mkdir(parents=True, exist_ok=False)
    report = work / "junit.xml"
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "--quiet",
        "--disable-warnings",
        "-p",
        "no:cacheprovider",
        f"--junitxml={report}",
        "tests",
    ]
    started = monotonic_ns()
    try:
        exit_code, _stdout, _stderr, timed_out = _run_process(
            argv,
            cwd=source,
            env=environment,
            timeout_seconds=PYTEST_TIMEOUT_SECONDS,
        )
    except OSError as error:
        raise BenchmarkError("the existing pytest suite could not be launched") from error
    wall_time_ns = monotonic_ns() - started
    if timed_out:
        raise BenchmarkError("the existing pytest suite timed out")
    if exit_code not in {0, 1}:
        raise BenchmarkError("the existing pytest suite returned an unsupported exit code")
    counts = _junit_counts(report)
    failed = counts[1] + counts[2] + counts[3] != 0
    if (exit_code == 0 and failed) or (exit_code == 1 and not failed):
        raise BenchmarkError("pytest exit status differs from its JUnit report")
    return PytestMeasurement(
        outcome=CheckOutcome.FAIL if failed else CheckOutcome.PASS,
        test_count=sum(counts),
        passed_count=counts[0],
        failed_count=counts[1],
        error_count=counts[2],
        skipped_count=counts[3],
        wall_time_ns=wall_time_ns,
    )


def _junit_counts(report: Path) -> tuple[int, int, int, int]:
    try:
        if not report.is_file() or report.stat().st_size > MAX_JUNIT_BYTES:
            raise BenchmarkError("pytest did not produce a bounded JUnit report")
        root = ElementTree.parse(report).getroot()
    except (OSError, ElementTree.ParseError) as error:
        raise BenchmarkError("pytest produced an invalid JUnit report") from error
    cases = [element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "testcase"]
    identities = [(case.get("classname"), case.get("name")) for case in cases]
    if not cases or len(set(identities)) != len(cases) or any(None in item for item in identities):
        raise BenchmarkError("pytest JUnit cases are missing or ambiguous")
    failed = errors = skipped = 0
    for case in cases:
        children = {child.tag.rsplit("}", 1)[-1] for child in case}
        if len(children & {"failure", "error", "skipped"}) > 1:
            raise BenchmarkError("pytest JUnit case has conflicting outcomes")
        failed += "failure" in children
        errors += "error" in children
        skipped += "skipped" in children
    passed = len(cases) - failed - errors - skipped
    return passed, failed, errors, skipped


def _measure_sequential(source: Path) -> SequentialMeasurement:
    started = monotonic_ns()
    try:
        namespace = runpy.run_path(str(source / "app" / "credits.py"))
        handler = cast(
            Callable[[_SequentialStore, FixtureEvent], None],
            namespace["apply_credit"],
        )
        if not callable(handler):
            raise TypeError("apply_credit is not callable")
        event = load_event()
        store = _SequentialStore()
        handler(store, event)
        handler(store, event)
    except Exception as error:
        raise BenchmarkError("the trusted sequential duplicate check failed to execute") from error
    wall_time_ns = monotonic_ns() - started
    state = store.snapshot()
    exactly_once = state == StateCounts(
        balance_cents=event["amount_cents"],
        ledger_count=1,
        ledger_total_cents=event["amount_cents"],
        marker_count=1,
    )
    duplicate = state == StateCounts(
        balance_cents=event["amount_cents"] * 2,
        ledger_count=2,
        ledger_total_cents=event["amount_cents"] * 2,
        marker_count=1,
    )
    if not exactly_once and not duplicate:
        raise BenchmarkError("the sequential duplicate check reached an unsupported state")
    observation = (
        CrashObservation.EXACTLY_ONCE if exactly_once else CrashObservation.DUPLICATE_EFFECT
    )
    return SequentialMeasurement(
        outcome=CheckOutcome.PASS if exactly_once else CheckOutcome.FAIL,
        observation=observation,
        state=state,
        wall_time_ns=wall_time_ns,
    )


def _measure_crashcheck(
    result: object,
    capsule: ReproCapsule,
    measured: dict[str, tuple[FixtureVariant, str, PytestMeasurement, SequentialMeasurement]],
) -> dict[str, CrashMeasurement]:
    if not isinstance(result, CrashCheckResult):
        raise BenchmarkError("CrashCheck returned an unsupported result")
    if (
        result.transport is not TruthLabel.LOCAL
        or result.execution_status is not ExecutionStatus.COMPLETED
        or result.integrity_status is not IntegrityStatus.VALID
        or result.verdict is not CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
        or result.capsule_digest != capsule.digest
        or capsule.event_digest != EVENT_DIGEST
        or capsule.environment_digest != runner_environment_digest()
    ):
        raise BenchmarkError("CrashCheck did not return complete valid local evidence")
    if len(result.bindings) != len(FIXTURE_REFS):
        raise BenchmarkError("CrashCheck did not bind all three benchmark trees")
    bindings = {binding.source_ref: binding for binding in result.bindings}
    if set(bindings) != set(FIXTURE_REFS):
        raise BenchmarkError("CrashCheck bindings differ from the benchmark fixtures")

    measurements: dict[str, CrashMeasurement] = {}
    for ref in FIXTURE_REFS:
        binding = bindings[ref]
        expected_tree = measured[ref][1]
        role = _EXPECTED_ROLES[ref]
        expected_observation = _EXPECTED_OBSERVATIONS[ref]
        attempts = tuple(attempt for attempt in result.attempts if attempt.role is role)
        if binding.tree_digest != expected_tree or len(attempts) != CONFIRMATIONS:
            raise BenchmarkError("CrashCheck tree binding or confirmation count changed")
        _validate_attempts(attempts, capsule, binding.digest, expected_tree, expected_observation)
        observation_counts = Counter(attempt.observation for attempt in attempts)
        earliest_start = min(attempt.started_at for attempt in attempts)
        first_witness = min(attempt.ended_at for attempt in attempts)
        group_end = max(attempt.ended_at for attempt in attempts)
        attempt_metrics = tuple(
            CrashAttemptMeasurement(
                attempt=index,
                execution_status=attempt.execution_status,
                integrity_status=attempt.integrity_status,
                observation=attempt.observation,
                duration_ns=_duration_ns(attempt.started_at, attempt.ended_at),
                final_state=_state_from_attempt(attempt),
            )
            for index, attempt in enumerate(attempts, start=1)
        )
        measurements[ref] = CrashMeasurement(
            role=role,
            observation=expected_observation,
            observation_counts=tuple(
                ObservationCount(observation=observation, count=observation_counts[observation])
                for observation in CrashObservation
            ),
            completed_world_count=sum(
                attempt.execution_status is ExecutionStatus.COMPLETED for attempt in attempts
            ),
            valid_world_count=sum(
                attempt.integrity_status is IntegrityStatus.VALID for attempt in attempts
            ),
            unique_database_count=len({attempt.database_id for attempt in attempts}),
            unique_execution_nonce_count=len({attempt.execution_nonce for attempt in attempts}),
            unique_worker_nonce_count=len(
                {spawn.worker_nonce for attempt in attempts for spawn in attempt.spawns}
            ),
            unique_ipc_session_count=len(
                {spawn.ipc_session_id for attempt in attempts for spawn in attempt.spawns}
            ),
            time_to_first_witness_ns=_duration_ns(earliest_start, first_witness),
            wall_time_ns=_duration_ns(earliest_start, group_end),
            attempts=attempt_metrics,
        )
    return measurements


def _measure_hunt(result: CrashCheckResult, capsule: ReproCapsule) -> HuntMeasurement:
    receipts = result.hypothesis_receipts
    reproduced = tuple(receipt for receipt in receipts if receipt.reproduced)
    selected = tuple(receipt for receipt in receipts if receipt.selected)
    minimization = result.minimization_receipts
    if (
        result.capsule_digest != capsule.digest
        or result.engine_code_digest != capsule.engine_code_digest
        or len(receipts) != 2
        or any(receipt.attempt.role is not WorldRole.BASE for receipt in receipts)
        or any(
            receipt.attempt.execution_status is not ExecutionStatus.COMPLETED
            or receipt.attempt.integrity_status is not IntegrityStatus.VALID
            for receipt in receipts
        )
        or len(reproduced) != 1
        or len(selected) != 1
        or reproduced[0] != selected[0]
        or selected[0].hypothesis_id != "effect-commit-v1"
        or selected[0].fault_boundary is not FaultBoundary.EFFECT_COMMIT
        or capsule.fault_boundary is not selected[0].fault_boundary
        or len(minimization) != 1
        or not minimization[0].irreducible
        or minimization[0].reproduced
        or minimization[0].retained
        or capsule.minimization_trace != (minimization[0].trace_digest,)
        or any(
            attempt.execution_status is not ExecutionStatus.COMPLETED
            or attempt.integrity_status is not IntegrityStatus.VALID
            or attempt.observation is not CrashObservation.EXACTLY_ONCE
            for attempt in minimization[0].confirmations
        )
    ):
        raise BenchmarkError("CrashCheck hunt differs from the audited base-only search")
    earliest_start = min(receipt.attempt.started_at for receipt in receipts)
    minimization_start = min(attempt.started_at for attempt in minimization[0].confirmations)
    minimization_end = max(attempt.ended_at for attempt in minimization[0].confirmations)
    return HuntMeasurement(
        minimization_wall_time_ns=_duration_ns(minimization_start, minimization_end),
        time_to_first_witness_ns=_duration_ns(earliest_start, reproduced[0].attempt.ended_at),
        wall_time_ns=_duration_ns(
            earliest_start, max(receipt.attempt.ended_at for receipt in receipts)
        ),
    )


def _validate_attempts(
    attempts: tuple[AttemptReceipt, ...],
    capsule: ReproCapsule,
    binding_digest: str,
    tree_digest: str,
    expected_observation: CrashObservation,
) -> None:
    if (
        len({attempt.database_id for attempt in attempts}) != CONFIRMATIONS
        or len({attempt.execution_nonce for attempt in attempts}) != CONFIRMATIONS
        or len({spawn.worker_nonce for attempt in attempts for spawn in attempt.spawns})
        != CONFIRMATIONS * 2
        or len({spawn.ipc_session_id for attempt in attempts for spawn in attempt.spawns})
        != CONFIRMATIONS * 2
    ):
        raise BenchmarkError("CrashCheck worlds are not independently prepared")
    for attempt in attempts:
        if (
            attempt.execution_status is not ExecutionStatus.COMPLETED
            or attempt.integrity_status is not IntegrityStatus.VALID
            or attempt.observation is not expected_observation
            or attempt.capsule_digest != capsule.digest
            or attempt.contract_digest != capsule.contract_digest
            or attempt.binding_digest != binding_digest
            or attempt.tree_digest != tree_digest
            or attempt.post_execution_tree_digest != tree_digest
            or attempt.event_digest != capsule.event_digest
            or attempt.environment_digest != capsule.environment_digest
            or len(attempt.spawns) != 2
            or attempt.final_snapshot is None
        ):
            raise BenchmarkError("CrashCheck attempt evidence is incomplete or inconsistent")
        state = _state_from_attempt(attempt)
        amount = capsule.amount_cents
        expected_state = (
            StateCounts(
                balance_cents=amount * 2,
                ledger_count=2,
                ledger_total_cents=amount * 2,
                marker_count=1,
            )
            if expected_observation is CrashObservation.DUPLICATE_EFFECT
            else StateCounts(
                balance_cents=amount,
                ledger_count=1,
                ledger_total_cents=amount,
                marker_count=1,
            )
        )
        if state != expected_state:
            raise BenchmarkError("CrashCheck observation differs from the durable final state")


def _state_from_attempt(attempt: AttemptReceipt) -> StateCounts:
    snapshot = attempt.final_snapshot
    if snapshot is None:
        raise BenchmarkError("CrashCheck attempt has no final state")
    return StateCounts(
        balance_cents=snapshot.account_balance_cents,
        ledger_count=snapshot.event_ledger_count,
        ledger_total_cents=snapshot.event_ledger_total_cents,
        marker_count=snapshot.event_marker_count,
    )


def _duration_ns(started_at: datetime, ended_at: datetime) -> int:
    delta = ended_at - started_at
    return ((delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds) * 1_000


def _input_digest(
    commit: str,
    capsule_digest: str,
    engine_code_digest: str,
    event_digest: str,
    environment: BenchmarkEnvironment,
    hunt: HuntMeasurement,
    cases: tuple[BenchmarkCase, ...],
) -> str:
    return sha256_json(
        {
            "capsule_digest": capsule_digest,
            "confirmations_per_tree": CONFIRMATIONS,
            "engine_code_digest": engine_code_digest,
            "environment": environment,
            "event_digest": event_digest,
            "hunt": hunt.model_dump(
                mode="json",
                exclude={
                    "minimization_wall_time_ns",
                    "time_to_first_witness_ns",
                    "wall_time_ns",
                },
            ),
            "scenario_id": SCENARIO_ID,
            "schema_version": SCHEMA_VERSION,
            "source_commit": commit,
            "trees": [{"ref": case.ref, "tree_digest": case.tree_digest} for case in cases],
        }
    )


__all__ = [
    "BenchmarkCase",
    "BenchmarkEnvironment",
    "BenchmarkError",
    "BenchmarkResult",
    "CheckOutcome",
    "CrashAttemptMeasurement",
    "CrashMeasurement",
    "HuntMeasurement",
    "ObservationCount",
    "PytestMeasurement",
    "SequentialMeasurement",
    "StateCounts",
    "run_benchmark",
]
