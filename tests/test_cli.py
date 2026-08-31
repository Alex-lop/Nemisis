from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import nemisis.cli as cli
from nemisis import CrashCheckResult, CrashVerdict, replay
from nemisis.benchmark import BenchmarkError, BenchmarkResult
from nemisis.crash_models import ExecutionStatus, IntegrityStatus
from nemisis.crashcheck import CrashCheckError
from nemisis.live import live_configuration_blockers
from nemisis.models import TruthLabel


def test_live_mode_lists_blockers_and_never_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name in (
        "NEBIUS_API_KEY",
        "NEMISIS_CONTREE_ROOT_IMAGE",
        "CONTREE_PROFILE",
        "CONTREE_HOME",
        "XDG_CONFIG_HOME",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    blockers = live_configuration_blockers()
    assert {message.split()[0] for message in blockers} == {
        "NEBIUS_API_KEY",
        "NEMISIS_CONTREE_ROOT_IMAGE",
        "CONTREE_PROFILE",
    }

    output = tmp_path / "runs"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nemisis",
            "verify",
            "--fixture",
            "idempotency-retry",
            "--mode",
            "live",
            "--output-dir",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert "LIVE BLOCKED" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE, 0),
        (CrashVerdict.BUG_REPRODUCED, 1),
        (CrashVerdict.PATCH_FAILED_STILL_REPRODUCES, 1),
        (CrashVerdict.EVIDENCE_INCOMPLETE, 2),
        (CrashVerdict.UNSUPPORTED_TARGET, 2),
    ],
)
def test_crashcheck_exit_codes_are_stable(verdict: CrashVerdict, expected: int) -> None:
    assert cli._exit_code(verdict) == expected


def test_check_routes_arguments_artifacts_and_failure_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seen: dict[str, object] = {}

    def fake_check(
        base: str,
        candidate: str,
        scenario: str,
        corrected: str | None = None,
        mode: str = "local",
    ) -> CrashCheckResult:
        seen.update(
            base=base,
            candidate=candidate,
            scenario=scenario,
            corrected=corrected,
            mode=mode,
            artifact_root=Path(os.environ["NEMISIS_ARTIFACT_ROOT"]),
        )
        return cast(
            CrashCheckResult,
            SimpleNamespace(
                transport=TruthLabel.LOCAL,
                execution_status=ExecutionStatus.COMPLETED,
                integrity_status=IntegrityStatus.VALID,
                verdict=CrashVerdict.PATCH_FAILED_STILL_REPRODUCES,
                summary="candidate still reproduces",
                capsule_digest="c" * 64,
                engine_code_digest="e" * 64,
                engine_source_commit="a" * 40,
                hypothesis_receipts=(
                    SimpleNamespace(
                        hypothesis_id="effect-commit-v1",
                        fault_boundary=SimpleNamespace(value="effect-commit"),
                        selected=True,
                    ),
                    SimpleNamespace(
                        hypothesis_id="marker-commit-v1",
                        fault_boundary=SimpleNamespace(value="marker-commit"),
                        selected=False,
                    ),
                ),
                minimization_receipts=(
                    SimpleNamespace(
                        removed_fault=SimpleNamespace(value="effect-commit"),
                        confirmations=(SimpleNamespace(), SimpleNamespace()),
                        irreducible=True,
                    ),
                ),
                attempts=(),
                bindings=(),
                artifacts={"manifest": "runs/manifest.json"},
            ),
        )

    monkeypatch.setattr(cli, "check", fake_check)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nemisis",
            "check",
            "--base",
            "base-sha",
            "--candidate",
            "candidate-sha",
            "--corrected",
            "corrected-sha",
            "--output-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert seen == {
        "artifact_root": tmp_path,
        "base": "base-sha",
        "candidate": "candidate-sha",
        "corrected": "corrected-sha",
        "mode": "local",
        "scenario": "sqlite-credit-v1",
    }
    assert "NEMISIS_ARTIFACT_ROOT" not in os.environ
    output = capsys.readouterr()
    assert "verdict: PATCH_FAILED_STILL_REPRODUCES" in output.out
    assert f"capsule: {'c' * 64}" in output.out
    assert f"engine code digest: {'e' * 64}" in output.out
    assert f"engine source commit: {'a' * 40}" in output.out
    assert "hunt: 2 hypotheses -> selected effect-commit (effect-commit-v1)" in output.out
    assert (
        "minimization: deleted effect-commit; empty schedule was EXACTLY_ONCE in 2/2 fresh "
        "base worlds; deletion rejected; final fault actions 1/1 (fixture-only necessity proof)"
        in output.out
    )
    assert f"manifest: {(tmp_path / 'runs/manifest.json').resolve()}" in output.out
    assert "CrashCheck check started (LOCAL)" in output.err


def test_crash_result_makes_no_minimization_claim_for_incomplete_evidence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = cast(
        CrashCheckResult,
        SimpleNamespace(
            transport=TruthLabel.LOCAL,
            execution_status=ExecutionStatus.SETUP_ERROR,
            integrity_status=IntegrityStatus.INCOMPLETE,
            verdict=CrashVerdict.EVIDENCE_INCOMPLETE,
            summary="minimization incomplete",
            capsule_digest="c" * 64,
            engine_code_digest="e" * 64,
            engine_source_commit=None,
            hypothesis_receipts=(),
            minimization_receipts=(
                SimpleNamespace(
                    removed_fault=SimpleNamespace(value="effect-commit"),
                    confirmations=(SimpleNamespace(), SimpleNamespace()),
                    irreducible=False,
                ),
            ),
            attempts=(),
            bindings=(),
            artifacts={},
        ),
    )

    cli._print_crash_result(result, as_json=False)

    output = capsys.readouterr().out
    assert "minimization: empty-schedule evidence incomplete; no minimization claim" in output
    assert "final fault actions" not in output


def test_json_error_preserves_the_unsupported_target_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def unsupported(*args: object, **kwargs: object) -> CrashCheckResult:
        raise CrashCheckError("UNSUPPORTED_TARGET: no exact handler binding")

    monkeypatch.setattr(cli, "check", unsupported)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nemisis",
            "check",
            "--base",
            "base",
            "--candidate",
            "candidate",
            "--json",
        ],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    output = capsys.readouterr()
    assert output.out == (
        '{"message":"UNSUPPORTED_TARGET: no exact handler binding",'
        '"verdict":"UNSUPPORTED_TARGET"}\n'
    )
    assert "CrashCheck check started (LOCAL)" in output.err


def test_doctor_json_is_the_only_stdout_document(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["nemisis", "doctor", "--mode", "local", "--json"])

    cli.main()

    output = capsys.readouterr()
    assert output.err == ""
    assert '"mode":"LOCAL"' in output.out
    assert '"status":"READY"' in output.out


def test_generated_regression_public_imports_exist() -> None:
    assert CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE.value == "FIX_PROVEN_FOR_THIS_CAPSULE"
    assert callable(replay)


def test_benchmark_uses_default_output_without_changing_artifact_root(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    existing_artifact_root = tmp_path / "existing-artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(existing_artifact_root))
    seen: dict[str, object] = {}
    result = cast(
        BenchmarkResult,
        SimpleNamespace(result_digest="d" * 64, source_commit="a" * 40),
    )

    def fake_run_benchmark(output: Path) -> BenchmarkResult:
        seen["output"] = output
        seen["artifact_root"] = os.environ["NEMISIS_ARTIFACT_ROOT"]
        return result

    monkeypatch.setattr(cli, "run_benchmark", fake_run_benchmark)
    monkeypatch.setattr(sys, "argv", ["nemisis", "benchmark"])

    cli.main()

    assert seen == {
        "artifact_root": str(existing_artifact_root),
        "output": Path(".nemisis/benchmark.json"),
    }
    assert os.environ["NEMISIS_ARTIFACT_ROOT"] == str(existing_artifact_root)
    assert capsys.readouterr().out.splitlines() == [
        f"result: {Path('.nemisis/benchmark.json').resolve()}",
        f"digest: {'d' * 64}",
        f"source: {'a' * 40}",
    ]


def test_benchmark_json_is_the_exact_result_document(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    result = cast(BenchmarkResult, SimpleNamespace())
    document = b'{"result_digest":"bound-result","schema_version":"benchmark-v1"}'
    output = tmp_path / "benchmark.json"
    monkeypatch.setattr(cli, "run_benchmark", lambda path: result)

    def fake_canonical_json(value: object) -> bytes:
        assert value is result
        return document

    monkeypatch.setattr(cli, "canonical_json", fake_canonical_json)
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "benchmark", "--output", str(output), "--json"],
    )

    cli.main()

    captured = capsys.readouterr()
    assert captured.out == f"{document.decode()}\n"
    assert captured.err == ""


def test_benchmark_error_exits_two(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_benchmark(output: Path) -> BenchmarkResult:
        raise BenchmarkError(f"could not write {output}")

    monkeypatch.setattr(cli, "run_benchmark", fail_benchmark)
    monkeypatch.setattr(sys, "argv", ["nemisis", "benchmark"])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "EVIDENCE_INCOMPLETE: could not write .nemisis/benchmark.json" in captured.err


def test_ci_smoke_covers_both_surfaces_and_discovers_the_bound_capsule() -> None:
    workflow = (Path(__file__).parents[1] / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "nemisis verify" in workflow
    assert "nemisis check" in workflow
    assert "nemisis replay" in workflow
    assert "-mindepth 2 -maxdepth 2" in workflow
    assert "repros/double-credit/capsule.json" not in workflow


def test_action_example_pins_a_real_release_and_bounds_runtime() -> None:
    workflow = (Path(__file__).parents[1] / ".github/examples/crashcheck.yml").read_text(
        encoding="utf-8"
    )

    assert "Alex-lop/Nemisis@0fb4bc27e787b4749af27e79377dbcff0f98060b" in workflow
    assert "0123456789abcdef" not in workflow
    assert "timeout-minutes: 15" in workflow
