"""The crash-window map is the sweep without a verdict: clean windows for a tree the kernel can
attribute, the census's own refusal for one it cannot, and no capsule or run directory ever."""

from __future__ import annotations

from pathlib import Path

import pytest

from nemisis.mapping import MapResult, map_windows

CREDIT = "sqlite-credit-v1"
INVENTORY = "sqlite-inventory-v1"


@pytest.fixture(autouse=True)
def _artifact_root(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = Path(str(tmp_path)) / "artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(root))
    return root


def test_the_map_of_the_atomic_fix_has_one_clean_window() -> None:
    result = map_windows(f"fixture:{CREDIT}/atomic", CREDIT)
    assert result.mappable is True
    assert result.census_status == "COMPLETED"
    assert result.census_integrity == "VALID"
    assert result.census_refusal is None
    assert result.commits == ("credit_and_mark",)
    assert len(result.windows) == 1
    window = result.windows[0]
    assert window.kill_after_commit == 1
    assert window.operation == "credit_and_mark"
    assert window.after_retry is not None
    assert window.after_retry.subject_total == 2500


def test_a_mark_first_handler_maps_both_of_its_kill_points() -> None:
    result = map_windows(f"fixture:{CREDIT}/mark-first", CREDIT)
    assert result.mappable is True
    assert result.commits == ("mark_processed", "credit")
    assert [w.operation for w in result.windows] == ["mark_processed", "credit"]
    assert result.windows[0].after_retry is not None
    # The mark-first tree passes the boundary but loses the credit if killed before it commits;
    # the map shows the durable state at each kill point without judging it.
    assert result.windows[0].after_retry.subject_total == 0
    assert result.windows[1].after_retry is not None
    assert result.windows[1].after_retry.subject_total == 2500


def test_the_map_refuses_tail_bytes_at_the_census() -> None:
    result = map_windows(f"fixture:{CREDIT}/tail-bytes", CREDIT)
    assert result.mappable is True
    assert result.census_status == "INTEGRITY_ERROR"
    assert result.census_integrity == "INVALID"
    assert result.census_refusal is not None
    assert "last page" in result.census_refusal
    assert result.windows == ()


def test_the_map_refuses_a_write_around_the_store_at_the_census() -> None:
    result = map_windows(f"fixture:{CREDIT}/raw-sql", CREDIT)
    assert result.mappable is True
    assert result.census_status == "INTEGRITY_ERROR"
    assert "wrote around the trusted store" in (result.census_refusal or "")
    assert result.windows == ()


def test_a_map_issues_no_verdict_and_writes_no_run_directory(_artifact_root: Path) -> None:
    result = map_windows(f"fixture:{INVENTORY}/atomic", INVENTORY)
    assert isinstance(result, MapResult)
    # MapResult carries no CrashVerdict field at all.
    assert "verdict" not in result.model_dump()
    # map_windows runs under its own temporary directory and keeps nothing under the artifact root.
    assert not (_artifact_root / "runs").exists()
    assert not (_artifact_root / "repros").exists()


def test_an_unbindable_tree_is_not_mappable(tmp_path: pytest.TempPathFactory) -> None:
    empty = Path(str(tmp_path)) / "no-handler"
    (empty / "app").mkdir(parents=True)
    (empty / "app" / "unrelated.py").write_text("x = 1\n", encoding="utf-8")
    result = map_windows(empty, CREDIT)
    assert result.mappable is False
    assert result.anchor_failure is not None
    assert result.tree_digest is None
    assert result.windows == ()
