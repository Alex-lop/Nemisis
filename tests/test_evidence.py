from __future__ import annotations

from pathlib import Path

import pytest

from nemisis.evidence import validate_manifest
from nemisis.local import verify_local
from nemisis.models import TruthLabel


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
