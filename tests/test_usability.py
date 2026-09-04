"""Small behaviours a judge trips over: typos, reruns, dirty trees, and blocked-run artifacts."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nemisis.crash_fixture import BUGGY_REF, MISLEADING_GREEN_REF, SCENARIO_ID, load_issue
from nemisis.crash_models import CrashVerdict
from nemisis.crashcheck import CrashCheckError, _materialize_source, check, initialize


def test_unknown_fixture_ref_names_the_known_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    with pytest.raises(CrashCheckError, match="known: fixture:sqlite-credit-v1/buggy"):
        check(BUGGY_REF, "fixture:sqlite-credit-v1/misleading_green", SCENARIO_ID, mode="local")


def test_init_is_idempotent_after_acceptance_and_names_the_remedy_otherwise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    issue = tmp_path / "issue.md"
    issue.write_text(load_issue(), encoding="utf-8")
    target = "app.credits:apply_credit"

    first = initialize(issue, target, BUGGY_REF, SCENARIO_ID)
    before = first.read_bytes()
    assert initialize(issue, target, BUGGY_REF, SCENARIO_ID) == first
    assert first.read_bytes() == before

    other = tmp_path / "other.md"
    other.write_text("# A different bug\n", encoding="utf-8")
    with pytest.raises(CrashCheckError, match="delete it to re-initialize"):
        initialize(other, target, BUGGY_REF, SCENARIO_ID)
    assert first.read_bytes() == before


def test_blocked_live_run_publishes_no_regression_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("NEBIUS_API_KEY", "CONTREE_PROFILE", "CONTREE_HOME", "NEMISIS_CONTREE_ROOT_IMAGE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty-config"))
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(artifacts))

    result = check(BUGGY_REF, MISLEADING_GREEN_REF, SCENARIO_ID, mode="live")

    assert result.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "regression_test" not in result.artifacts
    assert not list(artifacts.rglob("test_repro.py"))
    assert (artifacts / result.artifacts["capsule"]).is_file()


def test_dirty_working_tree_warns_that_the_commit_was_evaluated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.email", "t@example.invalid"], check=True)
    subprocess.run([*git, "config", "user.name", "t"], check=True)
    (repo / "app.py").write_text("committed\n", encoding="utf-8")
    subprocess.run([*git, "add", "app.py"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
    (repo / "app.py").write_text("edited but not committed\n", encoding="utf-8")
    monkeypatch.chdir(repo)

    source = _materialize_source("HEAD", tmp_path / "materialized")

    assert (source.path / "app.py").read_text(encoding="utf-8") == "committed\n"
    assert "uncommitted changes" in capsys.readouterr().err
