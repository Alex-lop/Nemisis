"""Nemisis command-line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from nemisis.benchmark import BenchmarkError, BenchmarkResult, run_benchmark
from nemisis.crash_fixture import SCENARIO_ID
from nemisis.crash_models import CrashCheckResult, CrashVerdict
from nemisis.crashcheck import CrashCheckError, accept_contract, check, initialize, replay
from nemisis.doctor import DoctorResult, doctor
from nemisis.fixture import FIXTURE_ID
from nemisis.hashing import canonical_json
from nemisis.local import LocalVerification, verify_local
from nemisis.models import RuntimeMode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nemisis")
    commands = parser.add_subparsers(dest="command", required=True)

    verify = commands.add_parser("verify", help="run the original differential fixture")
    verify.add_argument("--fixture", default=FIXTURE_ID, choices=[FIXTURE_ID])
    verify.add_argument(
        "--mode", default=RuntimeMode.LOCAL.value, choices=[mode.value for mode in RuntimeMode]
    )
    verify.add_argument("--output-dir", type=Path, default=Path(".nemisis/runs"))

    init = commands.add_parser("init", help="write or accept a CrashCheck contract")
    init.add_argument("--issue", type=Path, required=True)
    init.add_argument("--target", required=True)
    init.add_argument("--base", required=True)
    init.add_argument("--scenario", default=SCENARIO_ID, choices=[SCENARIO_ID])
    init.add_argument("--accept-contract")
    init.add_argument("--json", action="store_true")

    crashcheck = commands.add_parser("check", help="run a crash/retry counterexample")
    crashcheck.add_argument("--base", required=True)
    crashcheck.add_argument("--candidate", default="HEAD")
    crashcheck.add_argument("--corrected")
    crashcheck.add_argument("--scenario", default=SCENARIO_ID)
    crashcheck.add_argument("--mode", default="local", choices=["local", "live"])
    crashcheck.add_argument("--output-dir", type=Path, default=Path(".nemisis"))
    crashcheck.add_argument("--json", action="store_true")

    replay_command = commands.add_parser("replay", help="replay an immutable Repro Capsule")
    replay_command.add_argument("capsule", type=Path)
    replay_command.add_argument("--source", required=True)
    replay_command.add_argument(
        "--role", default="candidate", choices=["base", "candidate", "corrected"]
    )
    replay_command.add_argument("--mode", default="local", choices=["local", "live"])
    replay_command.add_argument("--output-dir", type=Path, default=Path(".nemisis"))
    replay_command.add_argument("--json", action="store_true")

    doctor_command = commands.add_parser("doctor", help="check CrashCheck prerequisites")
    doctor_command.add_argument("--mode", default="local", choices=["local", "live"])
    doctor_command.add_argument("--json", action="store_true")

    benchmark = commands.add_parser("benchmark", help="run the audited CrashCheck benchmark")
    benchmark.add_argument("--output", type=Path, default=Path(".nemisis/benchmark.json"))
    benchmark.add_argument("--json", action="store_true")
    return parser


def _print_result(result: LocalVerification) -> None:
    manifest = result.manifest
    print(f"NEMISIS — {_truth_label(manifest.truth_label.value)}")
    print(f"run: {manifest.request.run_id}")
    print(f"bundle: {manifest.bundle.digest}")
    print()
    print(f"{'CLAIM / TEST':<42} {'EXPECTED':<16} {'BASE':<16} {'CANDIDATE':<16} VERDICT")
    for cell in manifest.matrix:
        identity = f"{cell.claim_id} / {cell.test_id}"
        print(
            f"{identity:<42} {cell.expected_relation.value:<16} "
            f"{cell.base_outcome.value:<16} {cell.candidate_outcome.value:<16} "
            f"{cell.classification.value}"
        )
    print()
    print(f"artifact: {manifest.artifact.status.value} — {manifest.artifact.reason}")
    print(f"manifest: {result.manifest_path.resolve()}")
    print(f"report: {result.report_path.resolve()}")


def _truth_label(value: str) -> str:
    return "LOCAL FIXTURE" if value == "FIXTURE" else value.replace("_", " ")


def _print_crash_result(
    result: CrashCheckResult, *, as_json: bool, artifact_root: Path | None = None
) -> None:
    if as_json:
        print(canonical_json(result).decode())
        return
    print(f"NEMISIS CRASHCHECK — {result.transport.value}")
    print(f"execution: {result.execution_status.value}")
    print(f"integrity: {result.integrity_status.value}")
    print(f"verdict: {result.verdict.value}")
    print(f"summary: {result.summary}")
    print(f"capsule: {result.capsule_digest}")
    print(f"engine code digest: {result.engine_code_digest}")
    if result.engine_source_commit is not None:
        print(f"engine source commit: {result.engine_source_commit}")
    if result.hypothesis_receipts:
        selected = next(
            (receipt for receipt in result.hypothesis_receipts if receipt.selected), None
        )
        selection = (
            f"selected {selected.fault_boundary.value} ({selected.hypothesis_id})"
            if selected is not None
            else "no witness selected"
        )
        print(f"hunt: {len(result.hypothesis_receipts)} hypotheses -> {selection}")
    if minimization_receipts := getattr(result, "minimization_receipts", ()):
        minimization = minimization_receipts[0]
        outcome = "irreducible" if minimization.irreducible else "incomplete"
        print(
            "minimization: removed fault replayed "
            f"{len(minimization.confirmations)}x -> {outcome}; final schedule 1/1 action"
        )
    representative = next(
        (
            attempt
            for attempt in result.attempts
            if attempt.role.value in {"candidate", "corrected"}
            and attempt.checkpoint_snapshot is not None
            and attempt.final_snapshot is not None
        ),
        None,
    )
    if representative is not None:
        checkpoint = representative.checkpoint_snapshot
        final = representative.final_snapshot
        if checkpoint is not None and final is not None:
            print(
                "timeline: "
                f"{checkpoint.account_balance_cents}¢ durable -> "
                f"signal {representative.kill_signal} -> fresh worker -> "
                f"{final.account_balance_cents}¢"
            )
    for binding in result.bindings:
        print(
            f"source: {binding.source_ref} -> {binding.resolved_source_identity} "
            f"(tree {binding.tree_digest})"
        )
    for name, path in sorted(result.artifacts.items()):
        projected = Path(path) if artifact_root is None else (artifact_root / path).resolve()
        print(f"{name}: {projected}")


def _print_doctor(result: DoctorResult, *, as_json: bool) -> None:
    if as_json:
        print(canonical_json(result).decode())
        return
    print(f"NEMISIS DOCTOR — {result['mode']} {result['status']}")
    for item in result["checks"]:
        print(f"{item['status']:<7} {item['name']}: {item['detail']}")


def _print_init(path: Path, *, as_json: bool) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload["contract"]
    result = {
        "config": str(path),
        "contract_digest": contract["digest"],
        "status": payload["status"],
    }
    if as_json:
        print(canonical_json(result).decode())
        return
    print(f"config: {result['config']}")
    print(f"contract: {result['contract_digest']}")
    print(f"status: {result['status']}")


def _print_benchmark(result: BenchmarkResult, output: Path, *, as_json: bool) -> None:
    if as_json:
        print(canonical_json(result).decode())
        return
    print(f"result: {output.resolve()}")
    print(f"digest: {result.result_digest}")
    print(f"source: {result.source_commit}")


def _exit_code(verdict: CrashVerdict) -> int:
    if verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE:
        return 0
    if verdict in {CrashVerdict.BUG_REPRODUCED, CrashVerdict.PATCH_FAILED_STILL_REPRODUCES}:
        return 1
    return 2


@contextmanager
def _artifact_root(path: Path) -> Iterator[None]:
    name = "NEMISIS_ARTIFACT_ROOT"
    previous = os.environ.get(name)
    os.environ[name] = str(path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _fail(message: str, *, as_json: bool = False) -> None:
    verdict = (
        "UNSUPPORTED_TARGET" if message.startswith("UNSUPPORTED_TARGET:") else "EVIDENCE_INCOMPLETE"
    )
    if as_json:
        print(canonical_json({"message": message, "verdict": verdict}).decode())
    else:
        print(f"{verdict}: {message}", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "verify":
            if args.mode == RuntimeMode.LOCAL.value:
                _print_result(verify_local(fixture_id=args.fixture, output_root=args.output_dir))
                return
            from nemisis.contree import ContreeBackendError
            from nemisis.live import live_configuration_blockers, verify_live
            from nemisis.nemotron import NemotronError

            blockers = live_configuration_blockers()
            if blockers:
                _fail(f"LIVE BLOCKED: {'; '.join(blockers)}. Local mode was not substituted.")
            try:
                _print_result(verify_live(fixture_id=args.fixture, output_root=args.output_dir))
            except (ContreeBackendError, NemotronError) as error:
                _fail(f"LIVE FAILED: {error}. Local mode was not substituted.")
            return

        if args.command == "init":
            path = initialize(args.issue, args.target, args.base, args.scenario)
            if args.accept_contract:
                accept_contract(args.accept_contract, path)
            _print_init(path, as_json=args.json)
            return

        if args.command == "doctor":
            doctor_result = doctor(args.mode)
            _print_doctor(doctor_result, as_json=args.json)
            if doctor_result["status"] != "READY":
                raise SystemExit(2)
            return

        if args.command == "benchmark":
            benchmark_result = run_benchmark(args.output)
            _print_benchmark(benchmark_result, args.output, as_json=args.json)
            return

        print(f"CrashCheck {args.command} started ({args.mode.upper()})", file=sys.stderr)
        with _artifact_root(args.output_dir):
            if args.command == "check":
                crash_result = check(
                    args.base,
                    args.candidate,
                    args.scenario,
                    corrected=args.corrected,
                    mode=args.mode,
                )
            else:
                crash_result = replay(args.capsule, args.source, role=args.role, mode=args.mode)
        _print_crash_result(
            crash_result,
            as_json=args.json,
            artifact_root=args.output_dir,
        )
        status = _exit_code(crash_result.verdict)
        if status:
            raise SystemExit(status)
    except (BenchmarkError, CrashCheckError, OSError, ValueError) as error:
        _fail(str(error), as_json=bool(getattr(args, "json", False)))
