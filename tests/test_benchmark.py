from __future__ import annotations

import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import nemisis.benchmark as benchmark_module
from nemisis.benchmark import BenchmarkError, BenchmarkResult, CheckOutcome, run_benchmark
from nemisis.crash_fixture import (
    ATOMIC_REF,
    BUGGY_REF,
    EVENT_DIGEST,
    FIXTURE_REFS,
    MISLEADING_GREEN_REF,
)
from nemisis.crash_models import (
    CrashObservation,
    CrashVerdict,
    ExecutionStatus,
    FaultBoundary,
    IntegrityStatus,
)
from nemisis.crashcheck import _audited_contract, _seal_capsule
from nemisis.hashing import canonical_json, sha256_json
from nemisis.sqlite_credit import runner_environment_digest

TREE_DIGESTS = {
    BUGGY_REF: "e0e3df5d3bdd0659fd4fcd7719c9047186eb2099dbab2bbb8092c1903a97c0b2",
    MISLEADING_GREEN_REF: ("3d79be420d3a92ee84ac66c15576d1fbfdb7ec3dba4f34dd9e6bfeb8489bf69f"),
    ATOMIC_REF: "ccdce21b146ff0146fd93f3aa86f3d047f937153215cae4e2ab80c92d93954de",
}


@pytest.fixture(scope="module")
def benchmark_runs(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[tuple[BenchmarkResult, Path], tuple[BenchmarkResult, Path]]:
    root = tmp_path_factory.mktemp("benchmark").resolve()
    first = root / "first.json"
    second = root / "second.json"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(benchmark_module, "source_commit", lambda: commit)
        monkeypatch.setenv("NEMISIS_ENGINE_SOURCE_COMMIT", commit)
        return (run_benchmark(first), first), (run_benchmark(second), second)


def test_measures_the_audited_three_tree_outcome_matrix(
    benchmark_runs: tuple[tuple[BenchmarkResult, Path], tuple[BenchmarkResult, Path]],
) -> None:
    result = benchmark_runs[0][0]
    cases = {case.ref: case for case in result.cases}

    assert tuple(case.ref for case in result.cases) == FIXTURE_REFS
    assert {ref: case.tree_digest for ref, case in cases.items()} == TREE_DIGESTS
    assert all(case.pytest.outcome is CheckOutcome.PASS for case in result.cases)
    assert all(case.pytest.test_count == case.pytest.passed_count == 1 for case in result.cases)

    for ref in FIXTURE_REFS:
        assert cases[ref].sequential.outcome is CheckOutcome.PASS
        assert cases[ref].sequential.observation is CrashObservation.EXACTLY_ONCE
        assert cases[ref].sequential.state.model_dump() == {
            "balance_cents": 2500,
            "ledger_count": 1,
            "ledger_total_cents": 2500,
            "marker_count": 1,
        }

    expected_crash = {
        BUGGY_REF: CrashObservation.DUPLICATE_EFFECT,
        MISLEADING_GREEN_REF: CrashObservation.DUPLICATE_EFFECT,
        ATOMIC_REF: CrashObservation.EXACTLY_ONCE,
    }
    for ref, expected in expected_crash.items():
        crash = cases[ref].crashcheck
        counts = {item.observation: item.count for item in crash.observation_counts}
        assert crash.observation is expected
        assert counts[expected] == 5
        assert sum(counts.values()) == 5
        assert crash.completed_world_count == crash.valid_world_count == 5
        assert crash.unique_database_count == crash.unique_execution_nonce_count == 5
        assert crash.unique_worker_nonce_count == crash.unique_ipc_session_count == 10
        assert all(item.execution_status is ExecutionStatus.COMPLETED for item in crash.attempts)
        assert all(item.integrity_status is IntegrityStatus.VALID for item in crash.attempts)
        assert all(item.observation is expected for item in crash.attempts)

    assert result.crashcheck_verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    assert result.hunt.model_dump(
        exclude={"minimization_wall_time_ns", "time_to_first_witness_ns", "wall_time_ns"}
    ) == {
        "role": "base",
        "attempted_world_count": 2,
        "completed_world_count": 2,
        "valid_world_count": 2,
        "reproducing_world_count": 1,
        "selected_world_count": 1,
        "selected_hypothesis_id": "effect-commit-v1",
        "selected_fault_boundary": FaultBoundary.EFFECT_COMMIT,
        "hypothesis_selection_ratio": 0.5,
        "minimization_trial_count": 1,
        "minimization_world_count": 2,
        "initial_fault_action_count": 1,
        "final_fault_action_count": 1,
        "minimization_ratio": 1.0,
    }
    assert result.hunt.time_to_first_witness_ns <= result.hunt.wall_time_ns


def test_binds_exact_source_capsule_environment_and_canonical_bytes(
    benchmark_runs: tuple[tuple[BenchmarkResult, Path], tuple[BenchmarkResult, Path]],
) -> None:
    result, output = benchmark_runs[0]
    commit = result.source_commit
    assert len(commit) == 40 and not commit.endswith("-dirty")
    assert result.event_digest == EVENT_DIGEST
    pre_hunt_capsule = _seal_capsule(_audited_contract())
    assert result.capsule_digest != pre_hunt_capsule.digest
    assert result.engine_code_digest == pre_hunt_capsule.engine_code_digest
    assert result.environment.crashcheck_environment_digest == runner_environment_digest()
    assert output.read_bytes() == canonical_json(result) + b"\n"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert BenchmarkResult.model_validate_json(output.read_bytes()) == result

    expected_input_digest = sha256_json(
        {
            "capsule_digest": result.capsule_digest,
            "confirmations_per_tree": 5,
            "engine_code_digest": result.engine_code_digest,
            "environment": result.environment,
            "event_digest": result.event_digest,
            "hunt": result.hunt.model_dump(
                mode="json",
                exclude={
                    "minimization_wall_time_ns",
                    "time_to_first_witness_ns",
                    "wall_time_ns",
                },
            ),
            "scenario_id": "sqlite-credit-v1",
            "schema_version": "nemisis.crashcheck.benchmark.v1",
            "source_commit": commit,
            "trees": [{"ref": case.ref, "tree_digest": case.tree_digest} for case in result.cases],
        }
    )
    assert result.input_digest == expected_input_digest


def test_repeated_runs_are_deterministic_except_for_measured_time(
    benchmark_runs: tuple[tuple[BenchmarkResult, Path], tuple[BenchmarkResult, Path]],
) -> None:
    first = _without_timings(benchmark_runs[0][0].model_dump(mode="json"))
    second = _without_timings(benchmark_runs[1][0].model_dump(mode="json"))
    assert first == second


def test_result_digest_and_strict_schema_reject_tampering(
    benchmark_runs: tuple[tuple[BenchmarkResult, Path], tuple[BenchmarkResult, Path]],
) -> None:
    payload = benchmark_runs[0][0].model_dump(mode="json")
    payload["cases"][0]["tree_digest"] = "0" * 64
    with pytest.raises(ValidationError, match="benchmark input digest mismatch"):
        BenchmarkResult.model_validate_json(canonical_json(payload))

    payload = benchmark_runs[0][0].model_dump(mode="json")
    payload["invented"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BenchmarkResult.model_validate_json(canonical_json(payload))

    payload = benchmark_runs[0][0].model_dump(mode="json")
    payload["cases"][0]["crashcheck"]["observation"] = CrashObservation.EXACTLY_ONCE
    payload["result_digest"] = sha256_json(
        {key: value for key, value in payload.items() if key != "result_digest"}
    )
    with pytest.raises(ValidationError, match="case outcome differs"):
        BenchmarkResult.model_validate_json(canonical_json(payload))


def test_fails_closed_without_an_exact_source_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path.resolve() / "result.json"
    monkeypatch.setattr(benchmark_module, "source_commit", lambda: None)

    with pytest.raises(BenchmarkError, match=r"clean exact source_commit\(\)"):
        run_benchmark(output)
    assert not output.exists()


def test_fails_closed_for_a_dirty_source_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path.resolve() / "result.json"
    monkeypatch.setattr(benchmark_module, "source_commit", lambda: f"{'a' * 40}-dirty")

    with pytest.raises(BenchmarkError, match=r"clean exact source_commit\(\)"):
        run_benchmark(output)
    assert not output.exists()


def _without_timings(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_timings(item)
            for key, item in value.items()
            if key
            not in {
                "crashcheck_wall_time_ns",
                "duration_ns",
                "minimization_wall_time_ns",
                "result_digest",
                "time_to_first_witness_ns",
                "wall_time_ns",
            }
        }
    if isinstance(value, list):
        return [_without_timings(item) for item in value]
    return value
