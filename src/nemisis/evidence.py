"""Fail-closed checks binding a manifest to its exact observed evidence."""

from __future__ import annotations

from nemisis.bundle import verify_bundle_digest
from nemisis.hashing import sha256_json
from nemisis.matrix import candidate_is_accepted, classify, summarize_claim
from nemisis.models import (
    ArtifactStatus,
    Classification,
    Outcome,
    RunManifest,
    RunState,
    RuntimeMode,
    TruthLabel,
    WorldKind,
)


def validate_manifest(manifest: RunManifest) -> None:
    request = manifest.request
    verify_bundle_digest(manifest.bundle)
    if request.requested_runtime_mode is not manifest.runtime_mode:
        raise ValueError("request and manifest runtime modes differ")
    generated_digest = sha256_json(
        [test.model_dump(mode="json") for test in manifest.bundle.generated_tests]
    )
    if manifest.bundle.model_id != (manifest.model_id or "local-fixture"):
        raise ValueError("verification bundle model binding mismatch")
    if manifest.bundle.prompt_template_digest != manifest.prompt_template_digest:
        raise ValueError("verification bundle prompt binding mismatch")
    if manifest.runtime_mode is RuntimeMode.LOCAL and (
        manifest.truth_label is not TruthLabel.FIXTURE
        or manifest.model_call is not None
        or manifest.model_id is not None
        or manifest.endpoint_region is not None
    ):
        raise ValueError("local runtime requires fixture-labelled local evidence")
    worlds = {world.world_id: world for world in manifest.worlds}
    if len(worlds) != len(manifest.worlds):
        raise ValueError("world IDs must be unique")
    base_worlds = [world for world in manifest.worlds if world.kind is WorldKind.BASE]
    candidate_worlds = [world for world in manifest.worlds if world.kind is WorldKind.CANDIDATE]
    if len(base_worlds) != 1 or len(candidate_worlds) != 1:
        raise ValueError("one base and one candidate world are required")
    base_world, candidate_world = base_worlds[0], candidate_worlds[0]
    if set(worlds) != {
        f"{request.run_id}:{WorldKind.BASE.value}",
        f"{request.run_id}:{WorldKind.CANDIDATE.value}",
    }:
        raise ValueError("world IDs do not match the bound run")
    if base_worlds[0].parent_world_id != candidate_worlds[0].parent_world_id:
        raise ValueError("base and candidate must descend from the same prepared world")
    if (
        base_world.patch_applied
        or base_world.resulting_tree_digest != request.base_digest
        or not candidate_world.patch_applied
        or candidate_world.resulting_tree_digest != manifest.candidate_tree_digest
    ):
        raise ValueError("world patch/tree lineage mismatch")
    for world in manifest.worlds:
        bindings = (
            world.base_digest == request.base_digest,
            world.candidate_patch_digest == request.candidate_patch_digest,
            world.ticket_digest == request.ticket_digest,
            world.model_id == (manifest.model_id or "local-fixture"),
            world.prompt_template_digest == manifest.prompt_template_digest,
            world.model_input_digest == manifest.bundle.model_input_digest,
            world.generated_test_digest == generated_digest,
            world.verification_bundle_digest == manifest.bundle.digest,
            world.attempt == manifest.current_attempt,
            world.runtime_label == manifest.truth_label,
        )
        if not all(bindings):
            raise ValueError(f"world evidence binding mismatch: {world.world_id}")
    if manifest.runtime_mode is RuntimeMode.LIVE:
        if manifest.truth_label is not TruthLabel.LIVE or manifest.model_call is None:
            raise ValueError("live manifests require genuine live model evidence")
        if manifest.model_call.model_id != manifest.model_id:
            raise ValueError("model call does not match manifest model")
        if manifest.model_call.truth_label is not TruthLabel.LIVE:
            raise ValueError("live model evidence is not labelled LIVE")
        if not manifest.model_call.schema_valid or manifest.model_call.outcome != "success":
            raise ValueError("live model call did not produce schema-valid success evidence")
        if manifest.model_call.endpoint_region != manifest.endpoint_region:
            raise ValueError("model call endpoint does not match manifest endpoint")
        if manifest.model_call.prompt_template_digest != manifest.prompt_template_digest:
            raise ValueError("model call does not match prompt template")
        if manifest.bundle.model_input_digest != manifest.model_call.input_digest:
            raise ValueError("verification bundle does not bind the model input")
        if (
            manifest.model_call.response_digest is None
            or manifest.bundle.model_response_digest != manifest.model_call.response_digest
        ):
            raise ValueError("verification bundle does not bind the model response")
        if any(world.image_uuid is None for world in manifest.worlds):
            raise ValueError("live worlds require immutable image UUIDs")
        if any(
            world.parent_operation_id is None
            or world.preparation_operation_id is None
            or world.bundle_object_id is None
            or world.bundle_archive_digest is None
            for world in manifest.worlds
        ):
            raise ValueError("live worlds require preparation and bundle provider IDs")
        if len({world.bundle_object_id for world in manifest.worlds}) != 1:
            raise ValueError("live worlds did not use the same uploaded verification bundle")
        if len({world.bundle_archive_digest for world in manifest.worlds}) != 1:
            raise ValueError("live worlds did not use byte-identical bundle archives")

    executions = {receipt.receipt_id: receipt for receipt in manifest.executions}
    if len(executions) != len(manifest.executions):
        raise ValueError("execution receipt IDs must be unique")
    for receipt in manifest.executions:
        if receipt.world_id not in worlds:
            raise ValueError(f"execution references an unknown world: {receipt.receipt_id}")
        if receipt.verification_bundle_digest != manifest.bundle.digest:
            raise ValueError(f"execution bundle mismatch: {receipt.receipt_id}")
        if manifest.runtime_mode is RuntimeMode.LIVE:
            world = worlds[receipt.world_id]
            if receipt.operation_id is None:
                raise ValueError(f"live execution lacks an operation ID: {receipt.receipt_id}")
            if receipt.source_image_uuid != world.image_uuid or receipt.result_image_uuid is None:
                raise ValueError(f"live execution image binding mismatch: {receipt.receipt_id}")
    bundled_tests = (*manifest.bundle.baseline_tests, *manifest.bundle.generated_tests)
    test_specs = {test.test_id: test for test in bundled_tests}
    active_receipts = [
        receipt
        for receipt in manifest.executions
        if receipt.attempt == manifest.current_attempt and not receipt.is_stale
    ]
    active_pairs = [(receipt.world_id, receipt.test_id) for receipt in active_receipts]
    expected_pairs = {
        (world.world_id, test.test_id) for world in manifest.worlds for test in bundled_tests
    }
    if len(active_pairs) != len(set(active_pairs)) or set(active_pairs) != expected_pairs:
        raise ValueError("current execution receipts do not cover the exact world/test matrix")
    for receipt in active_receipts:
        if (
            receipt.receipt_id != f"{receipt.world_id}:{receipt.test_id}"
            or receipt.runner_version != manifest.bundle.runner_version
            or receipt.command_id != manifest.bundle.runner_id
            or receipt.collection_status is not Outcome.PASS
        ):
            raise ValueError(f"execution runner binding mismatch: {receipt.receipt_id}")
    for world in manifest.worlds:
        receipts = [receipt for receipt in active_receipts if receipt.world_id == world.world_id]
        first = receipts[0]
        varying_fields = {"receipt_id", "test_id", "outcome"}
        common = first.model_dump(exclude=varying_fields)
        if any(receipt.model_dump(exclude=varying_fields) != common for receipt in receipts[1:]):
            raise ValueError(f"execution suite metadata differs within world: {world.world_id}")
        failed = any(
            receipt.outcome in {Outcome.ASSERTION_FAIL, Outcome.ERROR} for receipt in receipts
        )
        if (
            first.exit_code not in {0, 1}
            or (first.exit_code == 0 and failed)
            or (first.exit_code == 1 and not failed)
        ):
            raise ValueError(f"execution exit code contradicts outcomes: {world.world_id}")

    matrix_test_ids = [cell.test_id for cell in manifest.matrix]
    if len(matrix_test_ids) != len(test_specs) or set(matrix_test_ids) != set(test_specs):
        raise ValueError("matrix does not cover each verification-bundle test exactly once")
    for cell in manifest.matrix:
        test = test_specs.get(cell.test_id)
        if (
            test is None
            or cell.claim_id != test.claim_id
            or cell.expected_relation is not test.expected_relation
        ):
            raise ValueError(f"matrix test binding mismatch: {cell.test_id}")
        base = executions.get(cell.base_receipt_id)
        candidate = executions.get(cell.candidate_receipt_id)
        if base is None or candidate is None or base.is_stale or candidate.is_stale:
            raise ValueError(f"matrix uses missing or stale evidence: {cell.test_id}")
        if (
            base.attempt != manifest.current_attempt
            or candidate.attempt != manifest.current_attempt
        ):
            raise ValueError(f"matrix uses a superseded attempt: {cell.test_id}")
        if worlds[base.world_id].kind is not WorldKind.BASE:
            raise ValueError(f"matrix base receipt is not from the base world: {cell.test_id}")
        if worlds[candidate.world_id].kind is not WorldKind.CANDIDATE:
            raise ValueError(
                f"matrix candidate receipt is not from the candidate world: {cell.test_id}"
            )
        if (base.test_id, base.outcome) != (cell.test_id, cell.base_outcome):
            raise ValueError(f"matrix base result mismatch: {cell.test_id}")
        if (candidate.test_id, candidate.outcome) != (cell.test_id, cell.candidate_outcome):
            raise ValueError(f"matrix candidate result mismatch: {cell.test_id}")
        if (
            classify(cell.expected_relation, cell.base_outcome, cell.candidate_outcome)
            is not cell.classification
        ):
            raise ValueError(f"matrix classification mismatch: {cell.test_id}")
        if cell.evidence_complete is not (cell.classification is not Classification.INCOMPLETE):
            raise ValueError(f"matrix evidence completeness mismatch: {cell.test_id}")

    claim_results = tuple(
        summarize_claim(claim.claim_id, manifest.matrix) for claim in manifest.bundle.claims
    )
    if claim_results != manifest.claims:
        raise ValueError("claim results were not derived from the observed matrix")

    artifact = manifest.artifact
    if artifact.world_id != candidate_world.world_id:
        raise ValueError("artifact is not bound to the exact candidate world")
    artifact_bindings = (
        artifact.source_identity == request.source_identity,
        artifact.base_digest == request.base_digest,
        artifact.candidate_patch_digest == request.candidate_patch_digest,
        artifact.final_patch_digest == request.candidate_patch_digest,
        artifact.generated_test_digest == generated_digest,
        artifact.verification_bundle_digest == manifest.bundle.digest,
        artifact.producing_attempt == manifest.current_attempt,
        artifact.image_uuid == candidate_world.image_uuid,
    )
    if not all(artifact_bindings):
        raise ValueError("artifact evidence binding mismatch")
    if artifact.source_commit != manifest.source_commit:
        raise ValueError("artifact source commit differs from the producing manifest")
    artifact_receipts = [
        executions.get(receipt_id) for receipt_id in artifact.verification_receipt_ids
    ]
    if any(
        receipt is None
        or receipt.is_stale
        or receipt.attempt != manifest.current_attempt
        or receipt.world_id != artifact.world_id
        for receipt in artifact_receipts
    ):
        raise ValueError("artifact uses missing, stale, superseded, or wrong-world evidence")
    candidate_receipt_ids = {cell.candidate_receipt_id for cell in manifest.matrix}
    if set(artifact.verification_receipt_ids) != candidate_receipt_ids:
        raise ValueError("artifact is not bound to the full candidate evidence set")
    accepted = candidate_is_accepted(manifest.claims)
    if (artifact.status is ArtifactStatus.ACCEPTED) is not accepted:
        raise ValueError("artifact status disagrees with deterministic claim results")
    if manifest.state is not RunState.COMPLETE or manifest.terminal_reason != artifact.reason:
        raise ValueError("terminal run state does not match the artifact result")
