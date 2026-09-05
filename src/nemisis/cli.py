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
from nemisis.crash_models import ContractProposal, CrashCheckResult, CrashVerdict
from nemisis.crashcheck import CrashCheckError, accept_contract, check, initialize, replay
from nemisis.doctor import DoctorResult, doctor
from nemisis.fixture import FIXTURE_ID
from nemisis.hashing import canonical_json
from nemisis.local import LocalVerification, verify_local
from nemisis.models import RuntimeMode
from nemisis.report import money


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nemisis")
    commands = parser.add_subparsers(dest="command", required=True)

    ref_help = (
        "fixture:<scenario>/<variant>, a Git ref resolved to one exact commit, or a local "
        "directory copied and identified by its tree digest"
    )
    verify = commands.add_parser("verify", help="run the original differential fixture")
    verify.add_argument("--fixture", default=FIXTURE_ID, choices=[FIXTURE_ID])
    verify.add_argument(
        "--mode",
        default=RuntimeMode.LOCAL.value,
        choices=[mode.value for mode in RuntimeMode],
        help="local runs subprocesses here; live requires Token Factory and ConTree",
    )
    verify.add_argument(
        "--output-dir", type=Path, default=Path(".nemisis/runs"), help="where runs are written"
    )

    init = commands.add_parser("init", help="write or accept a CrashCheck contract")
    init.add_argument("--issue", type=Path, required=True, help="UTF-8 bug report file")
    init.add_argument(
        "--target", required=True, help="module:function handler, e.g. app.credits:apply_credit"
    )
    init.add_argument("--base", required=True, help=f"exact base source: {ref_help}")
    init.add_argument("--scenario", default=SCENARIO_ID, choices=[SCENARIO_ID])
    init.add_argument(
        "--accept-contract",
        metavar="DIGEST",
        help="accept the DRAFT whose digest init printed; re-seals it as LOCAL",
    )
    init.add_argument(
        "--nemotron",
        action="store_true",
        help="ask Nemotron on Token Factory to propose the contract from the issue and base only",
    )
    init.add_argument("--json", action="store_true")

    propose = commands.add_parser(
        "propose-patch",
        help="ask Nemotron on Token Factory to write the fix; the result is an ordinary candidate",
    )
    propose.add_argument("--issue", type=Path, required=True, help="UTF-8 bug report file")
    propose.add_argument("--base", required=True, help=f"exact base source: {ref_help}")
    propose.add_argument(
        "--out", type=Path, required=True, help="new directory for the candidate tree"
    )
    propose.add_argument("--scenario", default=SCENARIO_ID, choices=[SCENARIO_ID])
    propose.add_argument("--json", action="store_true")

    crashcheck = commands.add_parser("check", help="run a crash/retry counterexample")
    crashcheck.add_argument("--base", required=True, help=f"exact base source: {ref_help}")
    crashcheck.add_argument(
        "--candidate", default="HEAD", help=f"exact candidate source (default HEAD): {ref_help}"
    )
    crashcheck.add_argument("--corrected", help=f"optional known-good control: {ref_help}")
    crashcheck.add_argument(
        "--scenario",
        default=SCENARIO_ID,
        help=f"{SCENARIO_ID} (audited fixture contract) or a path to an accepted config.json",
    )
    crashcheck.add_argument(
        "--mode",
        default="local",
        choices=["local", "live"],
        help="local kills real subprocesses here; live is not yet connected and fails closed",
    )
    crashcheck.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".nemisis"),
        help="artifact root for runs/ and repros/",
    )
    crashcheck.add_argument("--json", action="store_true", help="print the result document only")

    replay_command = commands.add_parser("replay", help="replay an immutable Repro Capsule")
    replay_command.add_argument(
        "capsule", type=Path, help="path to a capsule.json printed by check"
    )
    replay_command.add_argument("--source", required=True, help=f"exact source to test: {ref_help}")
    replay_command.add_argument(
        "--role",
        default="candidate",
        choices=["base", "candidate", "corrected"],
        help="which verdict the source claims",
    )
    replay_command.add_argument("--mode", default="local", choices=["local", "live"])
    replay_command.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".nemisis"),
        help="artifact root for runs/ and repros/",
    )
    replay_command.add_argument(
        "--json", action="store_true", help="print the result document only"
    )

    doctor_command = commands.add_parser("doctor", help="check CrashCheck prerequisites")
    doctor_command.add_argument(
        "--mode",
        default="local",
        choices=["local", "live"],
        help="live adds secret-free checks for the Token Factory key, ConTree profile, and image",
    )
    doctor_command.add_argument("--json", action="store_true")

    benchmark = commands.add_parser("benchmark", help="run the audited CrashCheck benchmark")
    benchmark.add_argument(
        "--output",
        type=Path,
        default=Path(".nemisis/benchmark.json"),
        help="result file; timings enter its digest, so use a fresh path to regenerate",
    )
    benchmark.add_argument("--json", action="store_true", help="print the result document only")
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
    print(f"capsule digest: {result.capsule_digest}")
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
        print(f"hypotheses: {len(result.hypothesis_receipts)} run -> {selection}")
    if minimization_receipts := getattr(result, "minimization_receipts", ()):
        control = minimization_receipts[0]
        if control.sole_fault_action_necessary_for_fixture:
            confirmations = len(control.confirmations)
            print(
                f"control: base delivered the event twice with no kill in {confirmations}/"
                f"{confirmations} fresh worlds and ended exactly once; the duplicate needs the "
                "crash"
            )
        else:
            print(
                "control: the no-kill base delivery did not complete, so the duplicate is not "
                "attributed to the crash"
            )
    for sweep in getattr(result, "sweeps", ()):
        operations = sweep.census.first_delivery_operations
        points = ", ".join(
            f"#{attempt.kill_after_commit} -> "
            + (
                money(attempt.final_snapshot.account_balance_cents)
                if attempt.final_snapshot is not None
                else "no final state"
            )
            + f" {attempt.observation.value}"
            for attempt in sweep.attempts
        )
        print(
            f"sweep: {sweep.role.value} makes {len(operations)} store commit"
            f"{'s' if len(operations) != 1 else ''} ({', '.join(operations) or 'none observed'}); "
            f"killed after each: {points or 'census incomplete'} -> {sweep.observation.value}"
        )
    representative = next(
        (
            attempt
            for sweep in getattr(result, "sweeps", ())
            if sweep.observation.value != "EXACTLY_ONCE"
            for attempt in sweep.attempts
            if attempt.observation is sweep.observation and attempt.final_snapshot is not None
        ),
        None,
    ) or next(
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
            signal_name = (
                "SIGKILL"
                if representative.kill_signal == 9
                else f"signal {representative.kill_signal}"
            )
            kill_point = (
                f" (after commit {representative.kill_after_commit})"
                if getattr(representative, "kill_after_commit", None) is not None
                else ""
            )
            print(
                "timeline: "
                f"{money(checkpoint.account_balance_cents)} durable{kill_point} -> "
                f"{signal_name} -> fresh worker -> {money(final.account_balance_cents)}"
            )
    author = getattr(result, "candidate_author", None)
    if author is not None:
        print(
            f"author: {author.model_call.model_id} ({author.model_call.truth_label.value}) wrote "
            f"{author.handler_path}; receipt {author.digest}"
        )
    for binding in result.bindings:
        print(
            f"source: {binding.source_ref} -> {binding.resolved_source_identity} "
            f"(tree {binding.tree_digest})"
        )
    for name, path in sorted(result.artifacts.items()):
        projected = Path(path) if artifact_root is None else artifact_root / path
        print(f"{name}: {projected}")


def _print_doctor(result: DoctorResult, *, as_json: bool) -> None:
    if as_json:
        print(canonical_json(result).decode())
        return
    print(f"NEMISIS DOCTOR — {result['mode']} {result['status']}")
    for item in result["checks"]:
        print(f"{item['status']:<7} {item['name']}: {item['detail']}")


def _print_init(
    path: Path,
    *,
    as_json: bool,
    proposal: ContractProposal | None = None,
    proposal_path: Path | None = None,
    accepted_draft: str | None = None,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload["contract"]
    result: dict[str, object] = {
        "config": str(path),
        "contract_digest": contract["digest"],
        "status": payload["status"],
    }
    if accepted_draft is not None:
        result["accepted_draft_digest"] = accepted_draft
    if proposal is not None and proposal_path is not None:
        result["proposal"] = str(proposal_path)
        result["contract_proposal"] = proposal.model_dump(mode="json")
    if as_json:
        print(canonical_json(result).decode())
        return
    print(f"config: {result['config']}")
    if accepted_draft is not None:
        print(f"accepted draft: {accepted_draft}")
    print(f"contract: {result['contract_digest']}")
    print(f"status: {result['status']}")
    if proposal is not None and proposal_path is not None:
        from nemisis.proposal import describe

        receipt = proposal.model_call
        print(f"proposal: {proposal_path}")
        print(
            f"nemotron: {receipt.model_id} · {receipt.endpoint_region} · "
            f"{receipt.truth_label.value} · schema valid · {receipt.latency_ms} ms · "
            f"receipt {proposal.digest}"
        )
        print(f"proposed: {describe(proposal)}; accepted by deterministic catalog check")


def _print_benchmark(result: BenchmarkResult, output: Path, *, as_json: bool) -> None:
    if as_json:
        print(canonical_json(result).decode())
        return
    print(f"{'variant':<18} {'existing test':<14} {'call twice':<12} {'crash + retry':<18} worlds")
    for case in result.cases:
        crash = case.crashcheck
        print(
            f"{case.variant:<18} {case.pytest.outcome.value:<14} "
            f"{case.sequential.observation.value:<12} {crash.observation.value:<18} "
            f"{crash.valid_world_count}/{crash.attempted_world_count}"
        )
    print(f"crashcheck wall: {result.crashcheck_wall_time_ns / 1e9:.2f} s")
    print(f"result: {output.resolve()}")
    print(f"digest: {result.result_digest}")
    print(f"source: {result.source_commit}")


def _exit_code(verdict: CrashVerdict) -> int:
    if verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE:
        return 0
    if verdict in {
        CrashVerdict.BUG_REPRODUCED,
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES,
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN,
    }:
        return 1
    return 2


@contextmanager
def _artifact_root(path: Path) -> Iterator[None]:
    name = "NEMISIS_ARTIFACT_ROOT"
    previous = os.environ.get(name)
    os.environ[name] = str(path.resolve())
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _fail(message: str, *, as_json: bool = False, crashcheck: bool = True) -> None:
    """Exit 2. Only check/replay failures carry a CrashCheck verdict; the rest are plain errors."""
    if crashcheck:
        verdict = (
            "UNSUPPORTED_TARGET"
            if message.startswith("UNSUPPORTED_TARGET:")
            else "EVIDENCE_INCOMPLETE"
        )
        if as_json:
            print(canonical_json({"message": message, "verdict": verdict}).decode())
        else:
            print(f"{verdict}: {message}", file=sys.stderr)
    elif as_json:
        print(canonical_json({"error": message}).decode())
    else:
        print(f"ERROR: {message}", file=sys.stderr)
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
                _fail(
                    f"LIVE BLOCKED: {'; '.join(blockers)}. Local mode was not substituted.",
                    crashcheck=False,
                )
            try:
                _print_result(verify_live(fixture_id=args.fixture, output_root=args.output_dir))
            except (ContreeBackendError, NemotronError) as error:
                _fail(f"LIVE FAILED: {error}. Local mode was not substituted.", crashcheck=False)
            return

        if args.command == "init":
            proposal = None
            if args.nemotron:
                from nemisis.nemotron import NemotronError
                from nemisis.proposal import ProposalError, propose_contract

                try:
                    proposal = propose_contract(args.issue, args.target, args.base, args.scenario)
                except (NemotronError, ProposalError) as error:
                    _fail(
                        f"NEMOTRON PROPOSAL REJECTED: {error}. No contract was drafted.",
                        as_json=args.json,
                        crashcheck=False,
                    )
            path = initialize(args.issue, args.target, args.base, args.scenario)
            if args.accept_contract:
                accept_contract(args.accept_contract, path)
            proposal_path = None
            if proposal is not None:
                from nemisis.proposal import PROPOSAL_NAME, write_proposal

                proposal_path = write_proposal(proposal, path.with_name(PROPOSAL_NAME))
            _print_init(
                path,
                as_json=args.json,
                proposal=proposal,
                proposal_path=proposal_path,
                accepted_draft=args.accept_contract,
            )
            return

        if args.command == "propose-patch":
            from nemisis.agent_patch import PatchError, describe, propose_patch
            from nemisis.nemotron import NemotronError

            try:
                patch = propose_patch(args.issue, args.base, args.out, args.scenario)
            except (NemotronError, PatchError) as error:
                _fail(
                    f"NEMOTRON PATCH REJECTED: {error}. No candidate was written.",
                    as_json=args.json,
                    crashcheck=False,
                )
            if args.json:
                print(
                    canonical_json(
                        {
                            "candidate": str(args.out),
                            "patch_proposal": patch.model_dump(mode="json"),
                        }
                    ).decode()
                )
                return
            receipt = patch.model_call
            print(f"candidate: {args.out}")
            print(
                f"nemotron: {receipt.model_id} · {receipt.endpoint_region} · "
                f"{receipt.truth_label.value} · schema valid · {receipt.latency_ms} ms · "
                f"receipt {patch.digest}"
            )
            print(f"patch: {describe(patch)}")
            print(f"rationale: {patch.rationale}")
            print(f"next: nemisis check --base {args.base} --candidate {args.out} --mode local")
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
        _fail(
            str(error),
            as_json=bool(getattr(args, "json", False)),
            crashcheck=args.command in {"check", "replay"},
        )
