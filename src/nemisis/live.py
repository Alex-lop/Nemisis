"""The single genuine Nemotron + ConTree differential path."""

from __future__ import annotations

import gzip
import io
import os
import tarfile
import tempfile
import uuid
from datetime import UTC, datetime
from importlib import metadata, resources
from pathlib import Path

from contree_client import ProfileError, resolve_profile

from nemisis.bundle import build_bundle
from nemisis.contree import (
    ContreeBackend,
    ContreeConfigurationError,
    ContreeExecution,
    ContreeProtocolError,
)
from nemisis.evidence import validate_manifest
from nemisis.fixture import FIXTURE_ID, Fixture, load_fixture
from nemisis.hashing import sha256_bytes, sha256_json, sha256_text
from nemisis.junit import parse_junit
from nemisis.local import LocalVerification, materialize_repository, source_commit
from nemisis.matrix import candidate_is_accepted, make_cell, summarize_claim
from nemisis.models import (
    ArtifactReceipt,
    ArtifactStatus,
    CandidatePatchSpec,
    ExecutionReceipt,
    Outcome,
    ResourceMetrics,
    RunManifest,
    RunState,
    RuntimeMode,
    TruthLabel,
    VerificationBundle,
    VerificationRequest,
    WorldKind,
    WorldReceipt,
)
from nemisis.nemotron import NemotronClient, NemotronGeneration, NemotronResponseError
from nemisis.patches import apply_patch, validate_patch
from nemisis.report import write_html_report

ROOT_IMAGE_ENV = "NEMISIS_CONTREE_ROOT_IMAGE"
PROMPT_VERSION = "nemotron-claims-v1"
OUTPUT_LIMIT = 4_000


def live_configuration_blockers() -> tuple[str, ...]:
    blockers: list[str] = []
    if not os.getenv("NEBIUS_API_KEY"):
        blockers.append("NEBIUS_API_KEY is missing")
    if not os.getenv(ROOT_IMAGE_ENV):
        blockers.append(f"{ROOT_IMAGE_ENV} is missing")
    try:
        profile = resolve_profile()
    except ProfileError:
        blockers.append("CONTREE_PROFILE is missing or invalid")
    else:
        if profile.token is None or not profile.token.strip():
            blockers.append("CONTREE_PROFILE has no authentication token")
    return tuple(blockers)


def verify_live(
    *, fixture_id: str = FIXTURE_ID, output_root: Path = Path(".nemisis/runs")
) -> LocalVerification:
    root_image = os.getenv(ROOT_IMAGE_ENV)
    if not root_image or any(character.isspace() for character in root_image):
        raise ContreeConfigurationError(
            f"{ROOT_IMAGE_ENV} must name an immutable ConTree image with Python, Git, and pytest"
        )
    try:
        uuid.UUID(root_image)
    except ValueError:
        raise ContreeConfigurationError(
            f"{ROOT_IMAGE_ENV} must be an immutable image UUID, not a mutable tag"
        ) from None
    fixture = load_fixture(fixture_id)
    patch = validate_patch(
        fixture.candidate_patch,
        base_digest=fixture.base_digest,
        allowed_files=frozenset({"inventory.py"}),
    )
    applied_patch = _apply_candidate(fixture, patch)
    expected_candidate_digest = applied_patch.resulting_tree_digest
    if expected_candidate_digest is None:
        raise RuntimeError("validated candidate patch produced no tree digest")

    sandboxes = ContreeBackend.from_profile()
    model = NemotronClient()
    generation = model.generate(
        ticket=fixture.ticket,
        candidate_diff=fixture.candidate_patch.decode(),
        max_generated_tests=4,
    )
    bundle = _live_bundle(fixture, generation, root_image)
    request = _request(fixture, applied_patch.digest, len(generation.generated_tests))

    source_upload = sandboxes.upload_file(_archive(fixture.repository_files))
    patch_upload = sandboxes.upload_file(fixture.candidate_patch)
    bundle_upload = sandboxes.upload_file(_bundle_archive(bundle))
    common = sandboxes.prepare_common(root_image, source_upload)
    _require_success(common, "common-world preparation")
    base = sandboxes.derive_base(common.result_image_uuid)
    candidate = sandboxes.derive_candidate(common.result_image_uuid, patch_upload)
    _require_success(base, "base-world preparation")
    _require_success(candidate, "candidate patch application")
    if sandboxes.tree_digest(base) != request.base_digest:
        raise ContreeProtocolError("live base tree digest differs from the bound source")
    if sandboxes.tree_digest(candidate) != expected_candidate_digest:
        raise ContreeProtocolError("live candidate tree digest differs from the validated patch")

    base_run = sandboxes.execute_bundle(base.result_image_uuid, bundle_upload)
    candidate_run = sandboxes.execute_bundle(candidate.result_image_uuid, bundle_upload)
    _require_execution_world(base_run, base.result_image_uuid, "base")
    _require_execution_world(candidate_run, candidate.result_image_uuid, "candidate")
    base_outcomes, base_report_hash = _outcomes(sandboxes, base_run, bundle)
    candidate_outcomes, candidate_report_hash = _outcomes(sandboxes, candidate_run, bundle)
    run_id = f"live-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    generated_digest = sha256_json(
        [test.model_dump(mode="json") for test in bundle.generated_tests]
    )
    base_world = _world(
        run_id=run_id,
        kind=WorldKind.BASE,
        request=request,
        generation=generation,
        bundle=bundle,
        bundle_object_id=bundle_upload.uuid,
        bundle_archive_digest=bundle_upload.sha256,
        common=common,
        prepared=base,
        tree_digest=request.base_digest,
        generated_digest=generated_digest,
        patch_applied=False,
    )
    candidate_world = _world(
        run_id=run_id,
        kind=WorldKind.CANDIDATE,
        request=request,
        generation=generation,
        bundle=bundle,
        bundle_object_id=bundle_upload.uuid,
        bundle_archive_digest=bundle_upload.sha256,
        common=common,
        prepared=candidate,
        tree_digest=expected_candidate_digest,
        generated_digest=generated_digest,
        patch_applied=True,
    )
    base_receipts = _execution_receipts(
        world=base_world,
        execution=base_run,
        outcomes=base_outcomes,
        report_hash=base_report_hash,
        bundle=bundle,
    )
    candidate_receipts = _execution_receipts(
        world=candidate_world,
        execution=candidate_run,
        outcomes=candidate_outcomes,
        report_hash=candidate_report_hash,
        bundle=bundle,
    )
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
    claims = tuple(summarize_claim(claim.claim_id, cells) for claim in bundle.claims)
    accepted = candidate_is_accepted(claims)
    commit = source_commit()
    artifact = ArtifactReceipt(
        status=ArtifactStatus.ACCEPTED if accepted else ArtifactStatus.REJECTED,
        world_id=candidate_world.world_id,
        image_uuid=candidate_world.image_uuid,
        final_patch_digest=request.candidate_patch_digest,
        source_identity=request.source_identity,
        base_digest=request.base_digest,
        candidate_patch_digest=request.candidate_patch_digest,
        generated_test_digest=generated_digest,
        verification_bundle_digest=bundle.digest,
        verification_receipt_ids=tuple(receipt.receipt_id for receipt in candidate_receipts),
        producing_attempt=1,
        source_commit=commit,
        reason=(
            "Candidate survived every required relation in live Sandbox worlds."
            if accepted
            else "Candidate was rejected by observed live differential evidence."
        ),
    )
    manifest = RunManifest(
        request=request.model_copy(update={"run_id": run_id}),
        runtime_mode=RuntimeMode.LIVE,
        truth_label=TruthLabel.LIVE,
        endpoint_region=generation.receipt.endpoint_region,
        model_id=generation.receipt.model_id,
        prompt_template_version=PROMPT_VERSION,
        prompt_template_digest=generation.receipt.prompt_template_digest,
        model_call=generation.receipt,
        current_attempt=1,
        bundle=bundle,
        candidate_tree_digest=expected_candidate_digest,
        worlds=(base_world, candidate_world),
        executions=(*base_receipts, *candidate_receipts),
        matrix=cells,
        claims=claims,
        artifact=artifact,
        state=RunState.COMPLETE,
        terminal_reason=artifact.reason,
        source_commit=commit,
    )
    validate_manifest(manifest)
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True)
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    report_path = run_dir / "report.html"
    write_html_report(manifest, report_path)
    return LocalVerification(manifest, manifest_path, report_path)


def _request(fixture: Fixture, patch_digest: str, test_count: int) -> VerificationRequest:
    return VerificationRequest(
        run_id="live-pending",
        source_identity=f"fixture:{FIXTURE_ID}",
        base_ref="packaged-base-v1",
        base_digest=fixture.base_digest,
        candidate_patch_location="packaged:candidate.patch",
        candidate_patch_digest=patch_digest,
        ticket=fixture.ticket,
        ticket_digest=sha256_text(fixture.ticket),
        requested_runtime_mode=RuntimeMode.LIVE,
        max_generated_tests=test_count,
        repair_allowed=False,
    )


def _live_bundle(
    fixture: Fixture, generation: NemotronGeneration, root_image: str
) -> VerificationBundle:
    try:
        return build_bundle(
            claims=(fixture.claims[0], *generation.claims),
            baseline_tests=fixture.baseline_tests,
            generated_tests=generation.generated_tests,
            harness_files=fixture.harness_files,
            runner_version=f"pytest@contree-image:{root_image}",
            parser_digest=sha256_bytes(
                resources.files("nemisis").joinpath("junit.py").read_bytes()
            ),
            dependency_lock_digest=sha256_json(
                {
                    "contree_root_image": root_image,
                    "contree_client": metadata.version("contree-client"),
                }
            ),
            model_id=generation.receipt.model_id,
            prompt_template_digest=generation.receipt.prompt_template_digest,
            model_input_digest=generation.receipt.input_digest,
            model_response_digest=generation.receipt.response_digest,
        )
    except ValueError:
        raise NemotronResponseError(
            "Nemotron output could not form a trusted verification bundle"
        ) from None


def _apply_candidate(fixture: Fixture, patch: CandidatePatchSpec) -> CandidatePatchSpec:
    with tempfile.TemporaryDirectory(prefix="nemisis-candidate-") as temporary:
        world = Path(temporary) / "candidate"
        materialize_repository(fixture, world)
        return apply_patch(patch, world)


def _archive(files: tuple[tuple[str, bytes], ...]) -> bytes:
    output = io.BytesIO()
    with (
        gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        for name, content in sorted(files):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def _bundle_archive(bundle: VerificationBundle) -> bytes:
    files = tuple(
        (test.path, test.content.encode())
        for test in (*bundle.baseline_tests, *bundle.generated_tests)
    ) + tuple((file.path, file.content.encode()) for file in bundle.harness_files)
    return _archive(files)


def _require_success(execution: ContreeExecution, action: str) -> None:
    if execution.exit_code != 0:
        raise ContreeProtocolError(f"{action} returned exit code {execution.exit_code}")


def _outcomes(
    backend: ContreeBackend, execution: ContreeExecution, bundle: VerificationBundle
) -> tuple[dict[str, Outcome], str]:
    report = backend.junit_xml(execution)
    expected = {test.test_name for test in (*bundle.baseline_tests, *bundle.generated_tests)}
    with tempfile.TemporaryDirectory(prefix="nemisis-junit-") as temporary:
        path = Path(temporary) / "junit.xml"
        path.write_bytes(report)
        outcomes = parse_junit(path, expected, exit_code=execution.exit_code)
    _require_complete_outcomes(outcomes, expected)
    return outcomes, sha256_bytes(report)


def _require_complete_outcomes(outcomes: dict[str, Outcome], expected: set[str]) -> None:
    if outcomes.keys() != expected:
        raise ContreeProtocolError("ConTree JUnit report did not cover the exact test set")
    incomplete = sorted(
        name
        for name, outcome in outcomes.items()
        if outcome in {Outcome.ERROR, Outcome.TIMEOUT, Outcome.NOT_RUN}
    )
    if incomplete:
        raise ContreeProtocolError(
            f"ConTree JUnit report contains incomplete outcomes: {', '.join(incomplete)}"
        )


def _require_execution_world(
    execution: ContreeExecution, requested_image_uuid: str, label: str
) -> None:
    if execution.source_image_uuid != requested_image_uuid:
        raise ContreeProtocolError(
            f"ConTree {label} execution source image differs from its requested world"
        )


def _world(
    *,
    run_id: str,
    kind: WorldKind,
    request: VerificationRequest,
    generation: NemotronGeneration,
    bundle: VerificationBundle,
    bundle_object_id: str,
    bundle_archive_digest: str,
    common: ContreeExecution,
    prepared: ContreeExecution,
    tree_digest: str,
    generated_digest: str,
    patch_applied: bool,
) -> WorldReceipt:
    return WorldReceipt(
        world_id=f"{run_id}:{kind.value}",
        kind=kind,
        parent_world_id=common.result_image_uuid,
        parent_operation_id=common.operation_id,
        preparation_operation_id=prepared.operation_id,
        image_uuid=prepared.result_image_uuid,
        bundle_object_id=bundle_object_id,
        bundle_archive_digest=bundle_archive_digest,
        base_digest=request.base_digest,
        candidate_patch_digest=request.candidate_patch_digest,
        ticket_digest=request.ticket_digest,
        model_id=generation.receipt.model_id,
        prompt_template_digest=generation.receipt.prompt_template_digest,
        model_input_digest=generation.receipt.input_digest,
        generated_test_digest=generated_digest,
        verification_bundle_digest=bundle.digest,
        patch_applied=patch_applied,
        resulting_tree_digest=tree_digest,
        runtime_label=TruthLabel.LIVE,
        attempt=1,
    )


def _execution_receipts(
    *,
    world: WorldReceipt,
    execution: ContreeExecution,
    outcomes: dict[str, Outcome],
    report_hash: str,
    bundle: VerificationBundle,
) -> tuple[ExecutionReceipt, ...]:
    if world.image_uuid is None:
        raise ContreeProtocolError("live world lacks an immutable image UUID")
    _require_execution_world(execution, world.image_uuid, world.kind.value)
    expected = {test.test_name for test in (*bundle.baseline_tests, *bundle.generated_tests)}
    _require_complete_outcomes(outcomes, expected)
    if execution.ended_at is None or execution.duration_seconds is None:
        raise ContreeProtocolError("ConTree execution lacks duration/end timestamp evidence")
    stdout = _without_evidence_payload(execution.stdout or "")
    stderr = execution.stderr or ""
    collection = Outcome.PASS if execution.exit_code in {0, 1} else Outcome.ERROR
    metrics = dict(execution.metrics)
    resource_metrics = ResourceMetrics(provider_values=metrics)
    by_name = {test.test_name: test for test in (*bundle.baseline_tests, *bundle.generated_tests)}
    return tuple(
        ExecutionReceipt(
            receipt_id=f"{world.world_id}:{test.test_id}",
            test_id=test.test_id,
            world_id=world.world_id,
            operation_id=execution.operation_id,
            source_image_uuid=execution.source_image_uuid,
            result_image_uuid=execution.result_image_uuid,
            started_at=execution.started_at,
            ended_at=execution.ended_at,
            duration_ms=round(execution.duration_seconds * 1_000),
            exit_code=execution.exit_code,
            outcome=outcomes[name],
            collection_status=collection,
            stdout_excerpt=stdout[:OUTPUT_LIMIT],
            stderr_excerpt=stderr[:OUTPUT_LIMIT],
            stdout_hash=sha256_text(stdout),
            stderr_hash=sha256_text(stderr),
            result_report_hash=report_hash,
            metrics=resource_metrics,
            runner_version=bundle.runner_version,
            command_id=bundle.runner_id,
            verification_bundle_digest=bundle.digest,
            attempt=1,
        )
        for name, test in by_name.items()
    )


def _without_evidence_payload(stdout: str) -> str:
    return "\n".join(
        line for line in stdout.splitlines() if not line.startswith("NEMISIS_JUNIT_BASE64=")
    )
