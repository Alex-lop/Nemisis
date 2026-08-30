from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import cast

import pytest

import nemisis.crashcheck as crashcheck_module
from nemisis.crash_fixture import (
    ATOMIC_REF,
    BUGGY_REF,
    MISLEADING_GREEN_REF,
    SCENARIO_ID,
    load_issue,
    materialize_fixture,
)
from nemisis.crash_models import (
    CrashCheckResult,
    CrashObservation,
    CrashVerdict,
    ExecutionStatus,
    IntegrityStatus,
    ReproCapsule,
    RetryContract,
    WorldRole,
)
from nemisis.crashcheck import CrashCheckError, accept_contract, check, initialize, replay
from nemisis.hashing import canonical_json, sha256_json
from nemisis.local import source_commit
from nemisis.models import TruthLabel

_TREE_DIGESTS = (
    "e0e3df5d3bdd0659fd4fcd7719c9047186eb2099dbab2bbb8092c1903a97c0b2",
    "3d79be420d3a92ee84ac66c15576d1fbfdb7ec3dba4f34dd9e6bfeb8489bf69f",
    "ccdce21b146ff0146fd93f3aa86f3d047f937153215cae4e2ab80c92d93954de",
)
_CONFIG_PATH = Path(".nemisis/config.json")


@pytest.fixture(scope="module")
def hero(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, CrashCheckResult]:
    root = tmp_path_factory.mktemp("crashcheck-hero")
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(root))
        monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
        monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
        result = check(
            BUGGY_REF,
            MISLEADING_GREEN_REF,
            SCENARIO_ID,
            corrected=ATOMIC_REF,
        )
    return root, result


def test_three_tree_hero_runs_fifteen_fresh_worlds(
    hero: tuple[Path, CrashCheckResult],
) -> None:
    _, result = hero

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    assert result.transport is TruthLabel.LOCAL
    assert result.execution_status is ExecutionStatus.COMPLETED
    assert result.integrity_status is IntegrityStatus.VALID
    assert [binding.tree_digest for binding in result.bindings] == list(_TREE_DIGESTS)
    assert [binding.resolved_source_identity for binding in result.bindings] == [
        BUGGY_REF,
        MISLEADING_GREEN_REF,
        ATOMIC_REF,
    ]
    assert Counter(attempt.role for attempt in result.attempts) == {
        WorldRole.BASE: 5,
        WorldRole.CANDIDATE: 5,
        WorldRole.CORRECTED: 5,
    }
    assert {
        role: {attempt.observation for attempt in result.attempts if attempt.role is role}
        for role in WorldRole
    } == {
        WorldRole.BASE: {CrashObservation.DUPLICATE_EFFECT},
        WorldRole.CANDIDATE: {CrashObservation.DUPLICATE_EFFECT},
        WorldRole.CORRECTED: {CrashObservation.EXACTLY_ONCE},
    }
    assert len({attempt.database_id for attempt in result.attempts}) == 15
    assert len({attempt.execution_nonce for attempt in result.attempts}) == 15
    assert len(result.hypothesis_receipts) == 2
    hunt_attempts = [receipt.attempt for receipt in result.hypothesis_receipts]
    assert len({attempt.database_id for attempt in [*hunt_attempts, *result.attempts]}) == 17
    assert len({attempt.execution_nonce for attempt in [*hunt_attempts, *result.attempts]}) == 17
    assert sum(receipt.selected for receipt in result.hypothesis_receipts) == 1
    assert all(
        len(attempt.spawns) == 2
        and attempt.spawns[0].exit_code == -9
        and attempt.spawns[1].exit_code == 0
        for attempt in result.attempts
    )


def test_hero_artifacts_and_digests_are_exact(
    hero: tuple[Path, CrashCheckResult],
) -> None:
    root, result = hero
    repro = root / "repros/double-credit" / result.capsule_digest
    expected_paths = {
        "capsule": repro / "capsule.json",
        "contract": repro / "contract.json",
        "event": repro / "event.json",
        "hunt": repro / "hunt.json",
        "manifest": root / f"runs/{result.run_id}/manifest.json",
        "metadata": repro / "metadata.json",
        "regression_test": repro / "test_repro.py",
        "report": root / f"runs/{result.run_id}/report.html",
    }

    assert result.artifacts == {
        name: path.relative_to(root).as_posix() for name, path in expected_paths.items()
    }
    assert all(path.is_file() for path in expected_paths.values())
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in expected_paths.values())
    assert result.engine_source_commit == source_commit()
    assert result.digest == sha256_json(result.model_dump(mode="json", exclude={"digest"}))

    capsule = ReproCapsule.model_validate_json(expected_paths["capsule"].read_bytes())
    manifest = json.loads(expected_paths["manifest"].read_bytes())
    contract = RetryContract.model_validate_json(expected_paths["contract"].read_bytes())
    event = json.loads(expected_paths["event"].read_bytes())
    hunt = json.loads(expected_paths["hunt"].read_bytes())
    metadata = json.loads(expected_paths["metadata"].read_bytes())
    report = expected_paths["report"].read_text(encoding="utf-8")

    assert capsule.digest == result.capsule_digest
    assert capsule.contract_digest == contract.digest
    assert capsule.event_digest == sha256_json(event)
    assert (
        result.engine_code_digest
        == capsule.engine_code_digest
        == crashcheck_module.engine_code_digest()
    )
    assert len(capsule.minimization_trace) == 2
    assert all(capsule.minimization_trace)
    assert [item["trace_digest"] for item in hunt["hypotheses"]] == list(capsule.minimization_trace)
    assert hunt["schema_version"] == "nemisis.crashcheck.hunt.v1"
    assert metadata == {
        "capsule_digest": capsule.digest,
        "contract_digest": contract.digest,
        "engine_code_digest": capsule.engine_code_digest,
        "fault_boundary": capsule.fault_boundary.value,
        "minimization_trace": list(capsule.minimization_trace),
        "regression_kind": "integration/fault",
        "schema_version": "nemisis.crashcheck.repro.v1",
        "truth_label": capsule.truth_label.value,
    }
    assert manifest["schema_version"] == "nemisis.crashcheck.run.v1"
    assert manifest["capsule"] == capsule.model_dump(mode="json")
    assert manifest["contract"] == contract.model_dump(mode="json")
    assert manifest["result"] == result.model_dump(mode="json")
    assert manifest["bindings"] == [item.model_dump(mode="json") for item in result.bindings]
    assert [item["resolved_source_identity"] for item in manifest["bindings"]] == [
        BUGGY_REF,
        MISLEADING_GREEN_REF,
        ATOMIC_REF,
    ]
    assert [item["resolved_source_identity"] for item in manifest["result"]["bindings"]] == [
        BUGGY_REF,
        MISLEADING_GREEN_REF,
        ATOMIC_REF,
    ]
    assert all(attempt.capsule_digest == capsule.digest for attempt in result.attempts)
    assert all(attempt.event_digest == capsule.event_digest for attempt in result.attempts)
    assert result.verdict.value in report
    assert capsule.digest in report


def test_complete_runs_keep_stable_capsule_bytes_and_semantic_trace(
    hero: tuple[Path, CrashCheckResult],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_root, first = hero
    second_root = tmp_path / "second-run"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(second_root))
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)

    second = check(BUGGY_REF, MISLEADING_GREEN_REF, SCENARIO_ID, corrected=ATOMIC_REF)

    first_capsule = ReproCapsule.model_validate_json(
        _artifact(first_root, first, "capsule").read_bytes()
    )
    second_capsule = ReproCapsule.model_validate_json(
        _artifact(second_root, second, "capsule").read_bytes()
    )
    assert first.execution_status is second.execution_status is ExecutionStatus.COMPLETED
    assert (
        _artifact(first_root, first, "capsule").read_bytes()
        == _artifact(second_root, second, "capsule").read_bytes()
    )
    assert first.capsule_digest == second.capsule_digest
    assert first_capsule.minimization_trace == second_capsule.minimization_trace
    assert _hunt_projection(first_root, first) == _hunt_projection(second_root, second)
    assert first.hypothesis_receipts != second.hypothesis_receipts


def test_candidate_input_cannot_change_base_only_hunt_or_capsule(
    hero: tuple[Path, CrashCheckResult],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_root, misleading = hero
    atomic_root = tmp_path / "atomic-candidate"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(atomic_root))
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)

    atomic = check(BUGGY_REF, ATOMIC_REF, SCENARIO_ID)

    assert misleading.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    assert atomic.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    assert misleading.capsule_digest == atomic.capsule_digest
    assert (
        _artifact(first_root, misleading, "capsule").read_bytes()
        == _artifact(atomic_root, atomic, "capsule").read_bytes()
    )
    assert _hunt_projection(first_root, misleading) == _hunt_projection(atomic_root, atomic)


def test_corrected_capsule_replay_uses_five_new_worlds(
    hero: tuple[Path, CrashCheckResult],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, original = hero
    repro_paths = [
        _artifact(root, original, name) for name in ("capsule", "event", "regression_test")
    ]
    original_inodes = [path.stat().st_ino for path in repro_paths]
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(root))

    result = replay(_artifact(root, original, "capsule"), ATOMIC_REF, role="corrected")

    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    assert result.capsule_digest == original.capsule_digest
    assert [result.artifacts[name] for name in ("capsule", "event", "regression_test")] == [
        original.artifacts[name] for name in ("capsule", "event", "regression_test")
    ]
    assert [path.stat().st_ino for path in repro_paths] == original_inodes
    assert len(result.attempts) == 5
    assert {attempt.role for attempt in result.attempts} == {WorldRole.CORRECTED}
    assert {attempt.observation for attempt in result.attempts} == {CrashObservation.EXACTLY_ONCE}
    assert len({attempt.database_id for attempt in result.attempts}) == 5
    assert len({attempt.execution_nonce for attempt in result.attempts}) == 5
    assert not {attempt.database_id for attempt in result.attempts} & {
        attempt.database_id for attempt in original.attempts
    }
    assert not {attempt.execution_nonce for attempt in result.attempts} & {
        attempt.execution_nonce for attempt in original.attempts
    }


def test_distinct_contract_capsules_publish_without_overwriting(
    hero: tuple[Path, CrashCheckResult],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, original = hero
    original_repro = _artifact(root, original, "capsule").parent
    original_files = {
        path.name: (path.read_bytes(), path.stat().st_ino) for path in original_repro.iterdir()
    }
    workspace = tmp_path / "contract-workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    issue = workspace / "issue.md"
    issue.write_text(load_issue() + "\nSecond accepted contract.\n", encoding="utf-8")
    config = initialize(issue, "app.credits:apply_credit", BUGGY_REF, SCENARIO_ID)
    payload = json.loads(config.read_bytes())
    accept_contract(payload["contract"]["digest"], config)
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(root))
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)

    second = check(BUGGY_REF, MISLEADING_GREEN_REF, config)

    second_repro = _artifact(root, second, "capsule").parent
    original_manifest = json.loads(_artifact(root, original, "manifest").read_bytes())
    second_manifest = json.loads(_artifact(root, second, "manifest").read_bytes())
    assert second.capsule_digest != original.capsule_digest
    assert second_manifest["contract"]["digest"] != original_manifest["contract"]["digest"]
    assert original_repro.name == original.capsule_digest
    assert second_repro.name == second.capsule_digest
    assert original_repro.parent == second_repro.parent
    assert original_repro != second_repro
    assert {path.name for path in second_repro.iterdir()} == {
        "capsule.json",
        "contract.json",
        "event.json",
        "hunt.json",
        "metadata.json",
        "test_repro.py",
    }
    assert {
        path.name: (path.read_bytes(), path.stat().st_ino) for path in original_repro.iterdir()
    } == original_files


def test_exported_regression_runs_from_a_clean_directory(
    hero: tuple[Path, CrashCheckResult],
    tmp_path: Path,
) -> None:
    _, result = hero
    clean = tmp_path / "clean"
    repro = clean / "repro"
    repro.mkdir(parents=True)
    for name in ("capsule", "contract", "regression_test"):
        shutil.copy2(_artifact(hero[0], result, name), repro)
    regression = repro / "test_repro.py"
    candidate = _run_exported_regression(
        regression,
        clean,
        clean / "candidate-artifacts",
        MISLEADING_GREEN_REF,
        "candidate",
    )
    corrected = _run_exported_regression(
        regression,
        clean,
        clean / "corrected-artifacts",
        ATOMIC_REF,
        "corrected",
    )

    assert candidate.returncode == 1, candidate.stdout + candidate.stderr
    assert "1 failed" in candidate.stdout
    assert corrected.returncode == 0, corrected.stdout + corrected.stderr
    assert "1 passed" in corrected.stdout
    assert list((clean / "candidate-artifacts/runs").glob("*/manifest.json"))
    assert list((clean / "corrected-artifacts/runs").glob("*/manifest.json"))


def test_live_blocker_never_falls_back_to_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "NEBIUS_API_KEY",
        "CONTREE_PROFILE",
        "CONTREE_HOME",
        "NEMISIS_CONTREE_ROOT_IMAGE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-config"))
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "live-artifacts"))

    result = check(BUGGY_REF, MISLEADING_GREEN_REF, SCENARIO_ID, mode="live")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert result.transport is TruthLabel.LIVE
    assert result.execution_status is ExecutionStatus.UNSUPPORTED
    assert result.integrity_status is IntegrityStatus.INCOMPLETE
    assert "Local execution was not substituted" in result.summary
    assert len(result.bindings) == len(result.attempts) == 1
    assert result.attempts[0].role is WorldRole.BASE
    assert result.attempts[0].spawns == ()
    assert result.attempts[0].observation is CrashObservation.NOT_OBSERVED


def test_anchor_binding_failure_is_a_scoped_crashcheck_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    issue = tmp_path / "issue.md"
    issue.write_text(load_issue(), encoding="utf-8")
    config = initialize(issue, "missing.handler:apply_credit", BUGGY_REF, SCENARIO_ID)
    payload = json.loads(config.read_bytes())
    accept_contract(payload["contract"]["digest"], config)

    with pytest.raises(
        CrashCheckError,
        match=r"^UNSUPPORTED_TARGET: target must have exactly one file binding",
    ):
        check(BUGGY_REF, MISLEADING_GREEN_REF, config)


def test_git_ref_ignores_base_owned_config_committed_after_contract_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = materialize_fixture(BUGGY_REF, tmp_path / "repository").path
    issue = repository / "issue.md"
    issue.write_text(load_issue(), encoding="utf-8")
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "crashcheck@example.invalid")
    _git(repository, "config", "user.name", "CrashCheck Test")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "base")
    original_base = _git(repository, "rev-parse", "HEAD")
    monkeypatch.chdir(repository)

    config = initialize(issue, "app.credits:apply_credit", original_base, SCENARIO_ID)
    payload = json.loads(config.read_bytes())
    contract = accept_contract(payload["contract"]["digest"], config)
    _git(repository, "add", ".nemisis/config.json")
    _git(repository, "commit", "-m", "configure crashcheck")
    configured_base = _git(repository, "rev-parse", "HEAD")
    candidate_tree = materialize_fixture(MISLEADING_GREEN_REF, tmp_path / "candidate-tree").path
    shutil.copy2(candidate_tree / "app/credits.py", repository / "app/credits.py")
    _git(repository, "add", "app/credits.py")
    _git(repository, "commit", "-m", "candidate")
    candidate = _git(repository, "rev-parse", "HEAD")
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "action-artifacts"))
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)

    result = check(configured_base, candidate, SCENARIO_ID)

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    assert result.bindings[0].tree_digest == contract.originating_base_tree_digest
    assert [binding.resolved_source_identity for binding in result.bindings] == [
        configured_base,
        candidate,
    ]
    assert len(result.attempts) == 10
    manifest = json.loads(_artifact(tmp_path / "action-artifacts", result, "manifest").read_bytes())
    assert [item["resolved_source_identity"] for item in manifest["bindings"]] == [
        configured_base,
        candidate,
    ]
    assert [item["resolved_source_identity"] for item in manifest["result"]["bindings"]] == [
        configured_base,
        candidate,
    ]


def test_default_scenario_uses_only_exact_directory_base_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = materialize_fixture(BUGGY_REF, tmp_path / "base").path
    candidate = materialize_fixture(MISLEADING_GREEN_REF, tmp_path / "candidate").path
    base_config, base_digest = _accepted_config(
        tmp_path / "base-config-workspace", base, "base-owned"
    )
    cwd_config, cwd_digest = _accepted_config(tmp_path / "cwd-workspace", base, "cwd-owned")
    candidate_config, candidate_digest = _accepted_config(
        tmp_path / "candidate-config-workspace", candidate, "candidate-owned"
    )
    (base / _CONFIG_PATH.parent).mkdir()
    (base / _CONFIG_PATH).write_bytes(base_config)
    (candidate / _CONFIG_PATH.parent).mkdir()
    (candidate / _CONFIG_PATH).write_bytes(candidate_config)
    cwd = tmp_path / "cwd-workspace"
    assert (cwd / _CONFIG_PATH).read_bytes() == cwd_config
    (cwd / SCENARIO_ID).write_bytes(cwd_config)
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "directory-artifacts"))
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)

    result = check(base, candidate, SCENARIO_ID)

    manifest = json.loads(
        _artifact(tmp_path / "directory-artifacts", result, "manifest").read_bytes()
    )
    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    assert manifest["contract"]["digest"] == base_digest
    assert manifest["contract"]["digest"] not in {cwd_digest, candidate_digest}
    assert [binding.tree_digest for binding in result.bindings] == list(_TREE_DIGESTS[:2])


def test_default_scenario_fails_when_exact_directory_base_has_no_config(
    tmp_path: Path,
) -> None:
    base = materialize_fixture(BUGGY_REF, tmp_path / "unconfigured-base").path

    with pytest.raises(
        CrashCheckError,
        match=r"^exact supplied base has no accepted \.nemisis/config\.json",
    ):
        check(base, MISLEADING_GREEN_REF, SCENARIO_ID)


def test_config_metadata_must_match_its_digest_bound_contract(
    tmp_path: Path,
) -> None:
    base = materialize_fixture(BUGGY_REF, tmp_path / "base").path
    content, _ = _accepted_config(tmp_path / "config-workspace", base, "base-owned")
    payload = json.loads(content)
    payload["target"] = "app.credits:other_handler"

    with pytest.raises(CrashCheckError, match="metadata contradicts"):
        crashcheck_module._load_config_bytes(canonical_json(payload))


def test_directory_source_materialization_enforces_a_total_byte_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "oversized-source"
    source.mkdir()
    (source / "handler.py").write_bytes(b"too large")
    monkeypatch.setattr(crashcheck_module, "MAX_SOURCE_ARCHIVE_BYTES", 1)

    with pytest.raises(CrashCheckError, match="file or byte limit"):
        crashcheck_module._materialize_source(source, tmp_path / "copy")


def test_local_source_root_symlink_is_rejected(tmp_path: Path) -> None:
    source = materialize_fixture(BUGGY_REF, tmp_path / "source").path
    linked = tmp_path / "linked-source"
    linked.symlink_to(source, target_is_directory=True)

    with pytest.raises(CrashCheckError, match="source root must not be a symlink"):
        check(linked, MISLEADING_GREEN_REF, SCENARIO_ID)


def test_git_source_archive_enforces_the_file_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = materialize_fixture(BUGGY_REF, tmp_path / "repository").path
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.email", "crashcheck@example.invalid")
    _git(repository, "config", "user.name", "CrashCheck Test")
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", "source")
    commit = _git(repository, "rev-parse", "HEAD")
    monkeypatch.chdir(repository)
    monkeypatch.setattr(crashcheck_module, "MAX_SOURCE_FILES", 1)

    with pytest.raises(
        CrashCheckError, match="Git source archive exceeds the supported file limit"
    ):
        crashcheck_module._materialize_source(commit, tmp_path / "copy")


@pytest.mark.parametrize(
    ("field", "value"),
    [("event_id", "evt_forged"), ("amount_cents", 1), ("engine_code_digest", "0" * 64)],
)
def test_forged_capsule_is_rejected_before_source_materialization(
    hero: tuple[Path, CrashCheckResult],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    root, result = hero
    capsule = ReproCapsule.model_validate_json(_artifact(root, result, "capsule").read_bytes())
    values = capsule.model_dump(mode="python", exclude={"digest"})
    values[field] = value
    if field in {"event_id", "amount_cents"}:
        values["event_digest"] = sha256_json(
            {
                "account_id": values["account_id"],
                "amount_cents": values["amount_cents"],
                "event_id": values["event_id"],
            }
        )
    forged = ReproCapsule.with_digest(**values)

    def materialize_must_not_run(*_args: object, **_kwargs: object) -> None:
        pytest.fail("source materialization ran before capsule validation")

    monkeypatch.setattr(crashcheck_module, "_materialize_source", materialize_must_not_run)
    with pytest.raises(CrashCheckError, match="fields differ from its accepted contract"):
        replay(forged, BUGGY_REF)


def test_evidence_write_is_exclusive_private_and_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "evidence.json"

    crashcheck_module._write_exact(path, b"sealed\n")
    inode = path.stat().st_ino
    crashcheck_module._write_exact(path, b"sealed\n")

    assert path.read_bytes() == b"sealed\n"
    assert path.stat().st_ino == inode
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(CrashCheckError, match="refusing to overwrite different evidence"):
        crashcheck_module._write_exact(path, b"different\n")


def test_evidence_replacement_is_atomic_and_private(tmp_path: Path) -> None:
    path = tmp_path / "evidence.json"
    crashcheck_module._write_exact(path, b"draft\n")
    draft_inode = path.stat().st_ino

    crashcheck_module._write_exact(path, b"accepted\n", replace=True)

    assert path.read_bytes() == b"accepted\n"
    assert path.stat().st_ino != draft_inode
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".evidence.json.*.tmp"))


def test_evidence_write_rejects_symlink_target_and_parent(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"outside\n")
    target = tmp_path / "target.json"
    target.symlink_to(outside)

    with pytest.raises(CrashCheckError, match="unsafe evidence target"):
        crashcheck_module._write_exact(target, b"replacement\n", replace=True)
    assert outside.read_bytes() == b"outside\n"

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(CrashCheckError, match="unsafe evidence parent"):
        crashcheck_module._write_exact(linked_parent / "evidence.json", b"sealed\n")
    assert not (real_parent / "evidence.json").exists()


def test_composite_action_uses_the_shipped_frozen_project() -> None:
    action = (Path(__file__).resolve().parents[1] / "action.yml").read_text(encoding="utf-8")

    assert 'uv run --project "$GITHUB_ACTION_PATH" --frozen nemisis' in action
    assert "uv tool run" not in action


def _run_exported_regression(
    regression: Path,
    cwd: Path,
    artifact_root: Path,
    source: str,
    role: str,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "NEMISIS_ARTIFACT_ROOT": str(artifact_root),
            "NEMISIS_REPRO_ROLE": role,
            "NEMISIS_REPRO_SOURCE": source,
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(regression)],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def _artifact(root: Path, result: CrashCheckResult, name: str) -> Path:
    return root / result.artifacts[name]


def _hunt_projection(root: Path, result: CrashCheckResult) -> list[dict[str, object]]:
    document = cast(dict[str, object], json.loads(_artifact(root, result, "hunt").read_bytes()))
    return cast(list[dict[str, object]], document["hypotheses"])


def _accepted_config(workspace: Path, source: Path, owner: str) -> tuple[bytes, str]:
    workspace.mkdir()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.chdir(workspace)
        issue = workspace / "issue.md"
        issue.write_text(load_issue() + f"\n{owner} contract.\n", encoding="utf-8")
        config = initialize(issue, "app.credits:apply_credit", source, SCENARIO_ID)
        payload = json.loads(config.read_bytes())
        contract = accept_contract(payload["contract"]["digest"], config)
        return config.read_bytes(), contract.digest


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    ).stdout.strip()
