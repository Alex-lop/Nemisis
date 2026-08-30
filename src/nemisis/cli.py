"""Nemisis command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from nemisis.fixture import FIXTURE_ID
from nemisis.local import LocalVerification, verify_local
from nemisis.models import RuntimeMode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nemisis")
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", help="differentially verify a candidate patch")
    verify.add_argument("--fixture", default=FIXTURE_ID, choices=[FIXTURE_ID])
    verify.add_argument(
        "--mode", default=RuntimeMode.LOCAL.value, choices=[mode.value for mode in RuntimeMode]
    )
    verify.add_argument("--output-dir", type=Path, default=Path(".nemisis/runs"))
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


def main() -> None:
    args = _parser().parse_args()
    if args.command == "verify" and args.mode == RuntimeMode.LOCAL.value:
        _print_result(verify_local(fixture_id=args.fixture, output_root=args.output_dir))
        return
    from nemisis.contree import ContreeBackendError
    from nemisis.live import live_configuration_blockers, verify_live
    from nemisis.nemotron import NemotronError

    blockers = live_configuration_blockers()
    if blockers:
        raise SystemExit(f"LIVE BLOCKED: {'; '.join(blockers)}. Local mode was not substituted.")
    try:
        _print_result(verify_live(fixture_id=args.fixture, output_root=args.output_dir))
    except (ContreeBackendError, NemotronError) as error:
        raise SystemExit(f"LIVE FAILED: {error}. Local mode was not substituted.") from None
