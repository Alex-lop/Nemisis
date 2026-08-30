"""Real local filesystem execution for the trusted checked-in fixture."""

from __future__ import annotations

import importlib.metadata
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from nemisis.bundle import build_bundle, materialize_bundle
from nemisis.evidence import validate_manifest
from nemisis.fixture import FIXTURE_ID, Fixture, load_fixture
from nemisis.hashing import sha256_bytes, sha256_json, sha256_text, sha256_tree
from nemisis.junit import parse_junit
from nemisis.matrix import candidate_is_accepted, make_cell, summarize_claim
from nemisis.models import (
    ArtifactReceipt,
    ArtifactStatus,
    ExecutionReceipt,
    Outcome,
    RunManifest,
    RunState,
    RuntimeMode,
    TruthLabel,
    VerificationBundle,
    VerificationRequest,
    WorldKind,
    WorldReceipt,
)
from nemisis.patches import apply_patch, validate_patch
from nemisis.report import write_html_report
from nemisis.safety import safe_destination, safe_relative_path

LOCAL_PROMPT_VERSION = "local-fixture-v1"
LOCAL_PROMPT_DIGEST = sha256_text(LOCAL_PROMPT_VERSION)
RUN_TIMEOUT_SECONDS = 30
OUTPUT_LIMIT = 4_000


@dataclass(frozen=True)
class LocalVerification:
    manifest: RunManifest
    manifest_path: Path
    report_path: Path


def verify_local(
    *, fixture_id: str = FIXTURE_ID, output_root: Path = Path(".nemisis/runs")
) -> LocalVerification:
    fixture = load_fixture(fixture_id)
    run_id = f"local-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    request = VerificationRequest(
        run_id=run_id,
        source_identity=f"fixture:{fixture_id}",
        base_ref="packaged-base-v1",
        base_digest=fixture.base_digest,
        candidate_patch_location="packaged:candidate.patch",
        candidate_patch_digest=sha256_bytes(fixture.candidate_patch),
        ticket=fixture.ticket,
        ticket_digest=sha256_text(fixture.ticket),
        requested_runtime_mode=RuntimeMode.LOCAL,
        max_generated_tests=len(fixture.generated_tests),
        repair_allowed=False,
    )
    bundle = build_bundle(
        claims=fixture.claims,
        baseline_tests=fixture.baseline_tests,
        generated_tests=fixture.generated_tests,
        harness_files=fixture.harness_files,
        runner_version=importlib.metadata.version("pytest"),
        parser_digest=sha256_bytes(resources.files("nemisis").joinpath("junit.py").read_bytes()),
        dependency_lock_digest=_environment_digest(),
        model_id="local-fixture",
        prompt_template_digest=LOCAL_PROMPT_DIGEST,
    )
    patch = validate_patch(
        fixture.candidate_patch,
        base_digest=fixture.base_digest,
        allowed_files=frozenset({"inventory.py"}),
    )

    with tempfile.TemporaryDirectory(prefix="nemisis-local-") as temporary:
        root = Path(temporary)
        prepared = root / "prepared"
        materialize_repository(fixture, prepared)
        if sha256_tree(prepared) != fixture.base_digest:
            raise RuntimeError("packaged fixture base digest changed while preparing the world")
        base = shutil.copytree(prepared, root / "base")
        candidate = shutil.copytree(prepared, root / "candidate")
        applied = apply_patch(patch, candidate)
        if applied.resulting_tree_digest is None:
            raise RuntimeError("validated candidate patch produced no tree digest")
        bundle_path = root / "bundle"
        materialize_bundle(bundle, bundle_path)
        base_world, base_receipts = _execute_world(
            request=request,
            bundle=bundle,
            world=base,
            bundle_path=bundle_path,
            kind=WorldKind.BASE,
            patch_applied=False,
        )
        candidate_world, candidate_receipts = _execute_world(
            request=request,
            bundle=bundle,
            world=candidate,
            bundle_path=bundle_path,
            kind=WorldKind.CANDIDATE,
            patch_applied=True,
        )
        if candidate_world.resulting_tree_digest != applied.resulting_tree_digest:
            raise RuntimeError("candidate world tree digest changed after patch application")

    base_by_test = {receipt.test_id: receipt for receipt in base_receipts}
    candidate_by_test = {receipt.test_id: receipt for receipt in candidate_receipts}
    cells = tuple(
        make_cell(
            claim_id=test.claim_id,
            test_id=test.test_id,
            expected=test.expected_relation,
            base=base_by_test[test.test_id].outcome,
            candidate=candidate_by_test[test.test_id].outcome,
            base_receipt_id=base_by_test[test.test_id].receipt_id,
            candidate_receipt_id=candidate_by_test[test.test_id].receipt_id,
        )
        for test in (*bundle.baseline_tests, *bundle.generated_tests)
    )
    claim_results = tuple(summarize_claim(claim.claim_id, cells) for claim in bundle.claims)
    accepted = candidate_is_accepted(claim_results)
    artifact = ArtifactReceipt(
        status=ArtifactStatus.ACCEPTED if accepted else ArtifactStatus.REJECTED,
        world_id=candidate_world.world_id,
        final_patch_digest=request.candidate_patch_digest,
        source_identity=request.source_identity,
        base_digest=request.base_digest,
        candidate_patch_digest=request.candidate_patch_digest,
        generated_test_digest=candidate_world.generated_test_digest,
        verification_bundle_digest=bundle.digest,
        verification_receipt_ids=tuple(receipt.receipt_id for receipt in candidate_receipts),
        producing_attempt=1,
        source_commit=source_commit(),
        reason=(
            "Candidate survived every required relation."
            if accepted
            else "Candidate is incomplete: at least one required relation was not supported."
        ),
    )
    manifest = RunManifest(
        request=request,
        runtime_mode=RuntimeMode.LOCAL,
        truth_label=TruthLabel.FIXTURE,
        endpoint_region=None,
        model_id=None,
        prompt_template_version=LOCAL_PROMPT_VERSION,
        prompt_template_digest=LOCAL_PROMPT_DIGEST,
        model_call=None,
        current_attempt=1,
        bundle=bundle,
        candidate_tree_digest=applied.resulting_tree_digest,
        worlds=(base_world, candidate_world),
        executions=(*base_receipts, *candidate_receipts),
        matrix=cells,
        claims=claim_results,
        artifact=artifact,
        state=RunState.COMPLETE,
        terminal_reason=artifact.reason,
        source_commit=source_commit(),
    )
    validate_manifest(manifest)
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    report_path = run_dir / "report.html"
    write_html_report(manifest, report_path)
    return LocalVerification(manifest, manifest_path, report_path)


def materialize_repository(fixture: Fixture, destination: Path) -> None:
    destination.mkdir()
    for relative, content in fixture.repository_files:
        path = safe_destination(destination, safe_relative_path(relative))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _execute_world(
    *,
    request: VerificationRequest,
    bundle: VerificationBundle,
    world: Path,
    bundle_path: Path,
    kind: WorldKind,
    patch_applied: bool,
) -> tuple[WorldReceipt, tuple[ExecutionReceipt, ...]]:
    world_id = f"{request.run_id}:{kind.value}"
    results = world.parent / f"results-{kind.value}"
    results.mkdir()
    report = results / "junit.xml"
    argv = [
        sys.executable
        if value == "python"
        else value.replace("__nemisis_bundle__", str(bundle_path)).replace(
            "__nemisis_results__", str(results)
        )
        for value in bundle.runner_argv
    ]
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONPATH": os.pathsep.join((str(bundle_path / "harness"), str(world))),
    }
    started_at = datetime.now(UTC)
    timed_out = False
    try:
        process = subprocess.run(
            argv,
            cwd=world,
            env=environment,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            check=False,
        )
        exit_code: int | None = process.returncode
        stdout, stderr = process.stdout, process.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        exit_code = None
        stdout, stderr = _timeout_text(error.stdout), _timeout_text(error.stderr)
    ended_at = datetime.now(UTC)
    expected = {test.test_name for test in (*bundle.baseline_tests, *bundle.generated_tests)}
    parse_exit = exit_code if exit_code in {0, 1} else 2
    observed = parse_junit(report, expected, timed_out=timed_out, exit_code=parse_exit)
    report_hash = sha256_bytes(report.read_bytes()) if report.is_file() else sha256_bytes(b"")
    tests = (*bundle.baseline_tests, *bundle.generated_tests)
    duration_ms = max(0, int((ended_at - started_at).total_seconds() * 1_000))
    collection_status = (
        Outcome.TIMEOUT if timed_out else Outcome.ERROR if parse_exit == 2 else Outcome.PASS
    )
    stdout_hash, stderr_hash = sha256_text(stdout), sha256_text(stderr)
    receipts = tuple(
        ExecutionReceipt(
            receipt_id=f"{world_id}:{test.test_id}",
            test_id=test.test_id,
            world_id=world_id,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            exit_code=exit_code,
            outcome=observed[test.test_name],
            collection_status=collection_status,
            stdout_excerpt=stdout[:OUTPUT_LIMIT],
            stderr_excerpt=stderr[:OUTPUT_LIMIT],
            stdout_hash=stdout_hash,
            stderr_hash=stderr_hash,
            result_report_hash=report_hash,
            runner_version=bundle.runner_version,
            command_id=bundle.runner_id,
            verification_bundle_digest=bundle.digest,
            attempt=1,
        )
        for test in tests
    )
    generated_digest = sha256_json(
        [test.model_dump(mode="json") for test in bundle.generated_tests]
    )
    parent_id = f"prepared:{request.base_digest[:16]}"
    world_receipt = WorldReceipt(
        world_id=world_id,
        kind=kind,
        parent_world_id=parent_id,
        base_digest=request.base_digest,
        candidate_patch_digest=request.candidate_patch_digest,
        ticket_digest=request.ticket_digest,
        model_id="local-fixture",
        prompt_template_digest=LOCAL_PROMPT_DIGEST,
        generated_test_digest=generated_digest,
        verification_bundle_digest=bundle.digest,
        patch_applied=patch_applied,
        resulting_tree_digest=sha256_tree(world),
        runtime_label=TruthLabel.FIXTURE,
        attempt=1,
    )
    return world_receipt, receipts


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _environment_digest() -> str:
    packages = {
        name: importlib.metadata.version(name) for name in ("nemisis", "pydantic", "pytest")
    }
    return sha256_json({"python": sys.version.split()[0], "packages": packages})


def source_commit() -> str | None:
    repository = Path(__file__).resolve().parents[2]
    if not (repository / ".git").exists():
        return None
    try:
        sha = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "status",
                "--porcelain",
                "--",
                "src",
                "pyproject.toml",
                "uv.lock",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return f"{sha}-dirty" if dirty else sha
