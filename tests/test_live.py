from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

import nemisis.live as live
from nemisis.contree import ContreeExecution, ContreeProtocolError
from nemisis.fixture import load_fixture
from nemisis.local import verify_local
from nemisis.models import ModelCallReceipt, Outcome, TruthLabel
from nemisis.nemotron import NemotronGeneration, NemotronResponseError
from nemisis.patches import validate_patch


def _execution(source: str = "world-image") -> ContreeExecution:
    now = datetime.now(UTC)
    return ContreeExecution(
        operation_id="operation-id",
        source_image_uuid=source,
        result_image_uuid="result-image",
        started_at=now,
        ended_at=now,
        duration_seconds=0,
        exit_code=0,
        stdout="",
        stderr="",
        metrics=(),
    )


def test_live_receipts_bind_requested_and_result_images(tmp_path: Path) -> None:
    manifest = verify_local(output_root=tmp_path).manifest
    bundle = manifest.bundle
    world = manifest.worlds[0].model_copy(update={"image_uuid": "world-image"})
    outcomes = {
        test.test_name: Outcome.PASS for test in (*bundle.baseline_tests, *bundle.generated_tests)
    }

    receipts = live._execution_receipts(
        world=world,
        execution=_execution(),
        outcomes=outcomes,
        report_hash="0" * 64,
        bundle=bundle,
    )

    assert {receipt.source_image_uuid for receipt in receipts} == {"world-image"}
    assert {receipt.result_image_uuid for receipt in receipts} == {"result-image"}
    with pytest.raises(ContreeProtocolError, match="requested world"):
        live._execution_receipts(
            world=world,
            execution=_execution("wrong-image"),
            outcomes=outcomes,
            report_hash="0" * 64,
            bundle=bundle,
        )


def test_incomplete_live_outcomes_fail_clearly() -> None:
    with pytest.raises(ContreeProtocolError, match="incomplete outcomes: broken"):
        live._require_complete_outcomes({"broken": Outcome.ERROR}, {"broken"})
    with pytest.raises(ContreeProtocolError, match="exact test set"):
        live._require_complete_outcomes({}, {"missing"})


def test_candidate_tree_digest_comes_from_applied_validated_patch() -> None:
    fixture = load_fixture()
    patch = validate_patch(
        fixture.candidate_patch,
        base_digest=fixture.base_digest,
        allowed_files=frozenset({"inventory.py"}),
    )

    applied = live._apply_candidate(fixture, patch)

    assert applied.digest == patch.digest
    assert applied.resolved_base_identity == fixture.base_digest
    assert applied.resulting_tree_digest is not None


def test_invalid_generated_bundle_is_a_nemotron_response_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_fixture()
    receipt = ModelCallReceipt(
        truth_label=TruthLabel.LIVE,
        timestamp=datetime.now(UTC),
        endpoint_region="global",
        model_id="model",
        input_digest="0" * 64,
        prompt_template_digest="1" * 64,
        outcome="success",
        schema_valid=True,
        response_digest="2" * 64,
    )
    generation = NemotronGeneration(
        claims=fixture.claims[1:],
        generated_tests=fixture.generated_tests,
        receipt=receipt,
    )
    monkeypatch.setattr(live, "build_bundle", Mock(side_effect=ValueError))

    with pytest.raises(NemotronResponseError, match="trusted verification bundle"):
        live._live_bundle(fixture, generation, "image")


def test_live_bundle_always_includes_required_fixture_claims() -> None:
    fixture = load_fixture()
    receipt = ModelCallReceipt(
        truth_label=TruthLabel.LIVE,
        timestamp=datetime.now(UTC),
        endpoint_region="global",
        model_id="model",
        input_digest="0" * 64,
        prompt_template_digest="1" * 64,
        outcome="success",
        schema_valid=True,
        response_digest="2" * 64,
    )
    bundle = live._live_bundle(
        fixture,
        NemotronGeneration(claims=(), generated_tests=(), receipt=receipt),
        "image",
    )

    assert {claim.claim_id for claim in bundle.claims} >= {
        "regression-suite",
        "duplicate-retry",
        "crash-retry",
    }
    assert {test.test_id for test in bundle.generated_tests} >= {
        "adversarial.duplicate",
        "adversarial.crash-retry",
    }
