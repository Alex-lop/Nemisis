from __future__ import annotations

from pathlib import Path

import pytest

from nemisis.bundle import build_bundle
from nemisis.evidence import validate_manifest
from nemisis.local import verify_local
from nemisis.matrix import summarize_claim
from nemisis.models import RunState, TruthLabel


def test_mismatched_or_stale_evidence_cannot_publish(tmp_path: Path) -> None:
    manifest = verify_local(output_root=tmp_path).manifest

    wrong_world = manifest.worlds[0].model_copy(update={"base_digest": "0" * 64})
    with pytest.raises(ValueError, match="world evidence binding mismatch"):
        validate_manifest(manifest.model_copy(update={"worlds": (wrong_world, manifest.worlds[1])}))

    wrong_prompt = manifest.model_copy(update={"prompt_template_digest": "0" * 64})
    with pytest.raises(ValueError, match="prompt binding mismatch"):
        validate_manifest(wrong_prompt)

    wrong_model_input = manifest.worlds[0].model_copy(update={"model_input_digest": "0" * 64})
    with pytest.raises(ValueError, match="world evidence binding mismatch"):
        validate_manifest(
            manifest.model_copy(update={"worlds": (wrong_model_input, manifest.worlds[1])})
        )

    candidate_id = manifest.matrix[0].candidate_receipt_id
    stale = tuple(
        receipt.model_copy(update={"is_stale": True})
        if receipt.receipt_id == candidate_id
        else receipt
        for receipt in manifest.executions
    )
    with pytest.raises(ValueError, match="exact world/test matrix"):
        validate_manifest(manifest.model_copy(update={"executions": stale}))

    wrong_artifact = manifest.artifact.model_copy(update={"final_patch_digest": "0" * 64})
    with pytest.raises(ValueError, match="artifact evidence binding mismatch"):
        validate_manifest(manifest.model_copy(update={"artifact": wrong_artifact}))


def test_bundle_tree_matrix_and_runner_metadata_are_exactly_bound(tmp_path: Path) -> None:
    manifest = verify_local(output_root=tmp_path).manifest

    changed_bundle = manifest.bundle.model_copy(
        update={"generated_tests": manifest.bundle.generated_tests[:-1]}
    )
    with pytest.raises(ValueError, match="verification bundle digest mismatch"):
        validate_manifest(manifest.model_copy(update={"bundle": changed_bundle}))

    wrong_candidate = manifest.worlds[1].model_copy(update={"patch_applied": False})
    with pytest.raises(ValueError, match="world patch/tree lineage mismatch"):
        validate_manifest(
            manifest.model_copy(update={"worlds": (manifest.worlds[0], wrong_candidate)})
        )

    wrong_cell = manifest.matrix[0].model_copy(update={"claim_id": "other-claim"})
    with pytest.raises(ValueError, match="matrix test binding mismatch"):
        validate_manifest(
            manifest.model_copy(update={"matrix": (wrong_cell, *manifest.matrix[1:])})
        )

    wrong_runner = manifest.executions[0].model_copy(update={"command_id": "other-runner"})
    with pytest.raises(ValueError, match="execution runner binding mismatch"):
        validate_manifest(
            manifest.model_copy(update={"executions": (wrong_runner, *manifest.executions[1:])})
        )


def test_local_evidence_cannot_be_relabeled_live(tmp_path: Path) -> None:
    manifest = verify_local(output_root=tmp_path).manifest
    relabeled_worlds = tuple(
        world.model_copy(update={"runtime_label": TruthLabel.LIVE}) for world in manifest.worlds
    )

    with pytest.raises(ValueError, match="local runtime requires fixture"):
        validate_manifest(
            manifest.model_copy(update={"truth_label": TruthLabel.LIVE, "worlds": relabeled_worlds})
        )


def test_manifest_rejects_contradictory_or_duplicate_derived_evidence(tmp_path: Path) -> None:
    manifest = verify_local(output_root=tmp_path).manifest

    wrong_exit = manifest.executions[0].model_copy(update={"exit_code": 2})
    with pytest.raises(ValueError, match="suite metadata differs"):
        validate_manifest(
            manifest.model_copy(update={"executions": (wrong_exit, *manifest.executions[1:])})
        )
    base_world = manifest.worlds[0].world_id
    failed_process = tuple(
        receipt.model_copy(update={"exit_code": 2}) if receipt.world_id == base_world else receipt
        for receipt in manifest.executions
    )
    with pytest.raises(ValueError, match="exit code contradicts outcomes"):
        validate_manifest(manifest.model_copy(update={"executions": failed_process}))

    duplicate_matrix = (manifest.matrix[0], *manifest.matrix)
    duplicate_claims = tuple(
        summarize_claim(claim.claim_id, duplicate_matrix) for claim in manifest.bundle.claims
    )
    with pytest.raises(ValueError, match="exactly once"):
        validate_manifest(
            manifest.model_copy(update={"matrix": duplicate_matrix, "claims": duplicate_claims})
        )

    incomplete = manifest.matrix[0].model_copy(update={"evidence_complete": False})
    with pytest.raises(ValueError, match="completeness mismatch"):
        validate_manifest(
            manifest.model_copy(update={"matrix": (incomplete, *manifest.matrix[1:])})
        )


def test_manifest_rejects_contradictory_terminal_provenance(tmp_path: Path) -> None:
    manifest = verify_local(output_root=tmp_path).manifest

    with pytest.raises(ValueError, match="terminal run state"):
        validate_manifest(manifest.model_copy(update={"state": RunState.INTAKE}))
    with pytest.raises(ValueError, match="terminal run state"):
        validate_manifest(manifest.model_copy(update={"terminal_reason": "invented"}))

    artifact = manifest.artifact.model_copy(update={"source_commit": "f" * 40})
    with pytest.raises(ValueError, match="source commit"):
        validate_manifest(manifest.model_copy(update={"artifact": artifact}))


def test_bundle_rejects_duplicate_harness_paths_and_claim_links(tmp_path: Path) -> None:
    bundle = verify_local(output_root=tmp_path).manifest.bundle
    with pytest.raises(ValueError, match="harness paths must be unique"):
        build_bundle(
            claims=bundle.claims,
            baseline_tests=bundle.baseline_tests,
            generated_tests=bundle.generated_tests,
            harness_files=(*bundle.harness_files, bundle.harness_files[0]),
            runner_version=bundle.runner_version,
            parser_digest=bundle.parser_digest,
            dependency_lock_digest=bundle.dependency_lock_digest,
            model_id=bundle.model_id,
            prompt_template_digest=bundle.prompt_template_digest,
        )

    duplicate_links = bundle.claims[0].model_copy(
        update={
            "linked_test_ids": (
                *bundle.claims[0].linked_test_ids,
                bundle.claims[0].linked_test_ids[0],
            )
        }
    )
    with pytest.raises(ValueError, match="claim test links must be unique"):
        build_bundle(
            claims=(duplicate_links, *bundle.claims[1:]),
            baseline_tests=bundle.baseline_tests,
            generated_tests=bundle.generated_tests,
            harness_files=bundle.harness_files,
            runner_version=bundle.runner_version,
            parser_digest=bundle.parser_digest,
            dependency_lock_digest=bundle.dependency_lock_digest,
            model_id=bundle.model_id,
            prompt_template_digest=bundle.prompt_template_digest,
        )
