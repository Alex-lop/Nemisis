from __future__ import annotations

import json
from pathlib import Path

import pytest

import nemisis.local as local_module
from nemisis.local import source_commit, verify_local
from nemisis.models import ArtifactStatus, Classification, Outcome, TruthLabel


def test_local_fixture_exposes_the_incomplete_candidate(tmp_path: Path) -> None:
    result = verify_local(output_root=tmp_path)
    manifest = result.manifest
    by_test = {cell.test_id: cell for cell in manifest.matrix}

    assert manifest.truth_label is TruthLabel.FIXTURE
    assert manifest.artifact.status is ArtifactStatus.REJECTED
    assert by_test["baseline.reserve"].classification is Classification.SUPPORTED
    assert by_test["baseline.out-of-stock"].classification is Classification.SUPPORTED
    assert by_test["adversarial.duplicate"].base_outcome is Outcome.ASSERTION_FAIL
    assert by_test["adversarial.duplicate"].candidate_outcome is Outcome.PASS
    assert by_test["adversarial.duplicate"].classification is Classification.SUPPORTED
    assert by_test["adversarial.crash-retry"].classification is Classification.UNRESOLVED
    assert {world.parent_world_id for world in manifest.worlds} == {
        f"prepared:{manifest.request.base_digest[:16]}"
    }
    assert {world.verification_bundle_digest for world in manifest.worlds} == {
        manifest.bundle.digest
    }
    assert {receipt.verification_bundle_digest for receipt in manifest.executions} == {
        manifest.bundle.digest
    }
    assert result.report_path.is_file()
    report = result.report_path.read_text()
    assert "LOCAL FIXTURE" in report
    assert manifest.bundle.digest in report
    assert "Execution receipts" in report
    persisted = json.loads(result.manifest_path.read_text())
    assert persisted["artifact"]["status"] == "REJECTED"


def test_installed_wheel_does_not_claim_the_callers_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_module = tmp_path / "site-packages" / "nemisis" / "local.py"
    monkeypatch.setattr(local_module, "__file__", str(fake_module))
    assert source_commit() is None
