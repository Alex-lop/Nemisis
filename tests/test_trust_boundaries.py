"""Truth labels come from code, never from input files; forks are refused on every surface."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nemisis.crash_fixture import BUGGY_REF, MISLEADING_GREEN_REF, SCENARIO_ID
from nemisis.crash_models import (
    CrashVerdict,
    ExecutionStatus,
    RetryContract,
    WorldRole,
)
from nemisis.crashcheck import (
    CrashCheckError,
    _audited_contract,
    _seal_capsule,
    check,
    replay,
)
from nemisis.hashing import canonical_json
from nemisis.models import TruthLabel


def _relabelled(
    *, accepted: bool, label: TruthLabel, issue_digest: str | None = None
) -> RetryContract:
    audited = _audited_contract()
    values = audited.model_dump(mode="python", exclude={"digest", "accepted", "truth_label"})
    if issue_digest is not None:
        values["issue_digest"] = issue_digest
    return RetryContract.with_digest(**values, accepted=accepted, truth_label=label)


def _write_config(path: Path, contract: RetryContract) -> Path:
    payload = {
        "base": contract.originating_base_ref,
        "contract": contract.model_dump(mode="json"),
        "issue": "issue.md",
        "scenario_id": contract.scenario_id,
        "schema_version": "1",
        "status": "ACCEPTED" if contract.accepted else "DRAFT",
        "target": contract.target,
    }
    path.write_bytes(canonical_json(payload) + b"\n")
    return path


@pytest.mark.parametrize(
    ("accepted", "label", "issue_digest"),
    [
        (True, TruthLabel.LIVE, None),
        (True, TruthLabel.RECORDED_LIVE, None),
        (True, TruthLabel.MOCKED, None),
        (True, TruthLabel.FIXTURE, "f" * 64),
        (False, TruthLabel.LOCAL, None),
        (False, TruthLabel.LIVE, None),
    ],
)
def test_config_cannot_stamp_a_truth_label_the_code_did_not_earn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    accepted: bool,
    label: TruthLabel,
    issue_digest: str | None,
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    config = _write_config(
        tmp_path / "config.json",
        _relabelled(accepted=accepted, label=label, issue_digest=issue_digest),
    )

    with pytest.raises(CrashCheckError, match="truth label"):
        check(BUGGY_REF, MISLEADING_GREEN_REF, config, mode="local")

    assert not (tmp_path / "artifacts").exists()


def test_locally_accepted_copy_of_the_audited_contract_is_local_not_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    config = _write_config(
        tmp_path / "config.json", _relabelled(accepted=True, label=TruthLabel.LOCAL)
    )

    result = check(BUGGY_REF, MISLEADING_GREEN_REF, config, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    manifest = json.loads(
        (tmp_path / "artifacts" / result.artifacts["manifest"]).read_text(encoding="utf-8")
    )
    assert manifest["capsule"]["truth_label"] == "LOCAL"
    assert manifest["contract"]["truth_label"] == "LOCAL"


def test_exported_capsule_contract_cannot_claim_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    contract = _relabelled(accepted=True, label=TruthLabel.LIVE)
    capsule = _seal_capsule(contract)
    repro = tmp_path / "repro"
    repro.mkdir()
    (repro / "capsule.json").write_bytes(canonical_json(capsule) + b"\n")
    (repro / "contract.json").write_bytes(canonical_json(contract) + b"\n")

    with pytest.raises(CrashCheckError, match="truth label"):
        replay(repro / "capsule.json", MISLEADING_GREEN_REF, role="candidate")

    assert not (tmp_path / "artifacts").exists()


def _pull_request_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, forked: bool) -> None:
    head = "someone-else/Nemisis" if forked else "Alex-lop/Nemisis"
    event = {
        "pull_request": {
            "head": {"repo": {"full_name": head}},
            "base": {"repo": {"full_name": "Alex-lop/Nemisis"}},
        }
    }
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(path))


def test_replay_refuses_an_untrusted_fork_before_spawning_any_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    _pull_request_event(tmp_path, monkeypatch, forked=True)

    result = replay(_seal_capsule(_audited_contract()), MISLEADING_GREEN_REF, role="candidate")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "untrusted fork" in result.summary
    assert len(result.attempts) == 1
    assert result.attempts[0].execution_status is ExecutionStatus.SETUP_ERROR
    assert result.attempts[0].spawns == ()


def test_check_refuses_an_untrusted_fork_after_freezing_the_base_witness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    _pull_request_event(tmp_path, monkeypatch, forked=True)

    result = check(BUGGY_REF, MISLEADING_GREEN_REF, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "untrusted fork" in result.summary
    assert {attempt.role for attempt in result.attempts} == {WorldRole.BASE}
    assert len(result.bindings) == 1


def test_same_repository_pull_request_is_not_treated_as_a_fork(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    _pull_request_event(tmp_path, monkeypatch, forked=False)

    result = replay(_seal_capsule(_audited_contract()), MISLEADING_GREEN_REF, role="candidate")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
