"""The crash-window map is the sweep without a verdict: clean windows for a tree the kernel can
attribute, the census's own refusal for one it cannot, and no capsule or run directory ever."""

from __future__ import annotations

from pathlib import Path

import pytest

from nemisis.mapping import MapResult, map_windows

CREDIT = "sqlite-credit-v1"
INVENTORY = "sqlite-inventory-v1"

# A handler that keeps a counter by absolute path outside every world: the first delivery (map's
# census) marks first, every later delivery (map's kill worlds) is atomic, so the kill worlds run
# a schedule the census never did. `check` refuses this with `_schedule_split`, so `map` must too.
SPLIT_SCHEDULE = """import os


def apply_credit(store, event):
    counter = "/var/tmp/nemisis-map-split-__TOKEN__"
    try:
        with open(counter, "r+", encoding="utf-8") as handle:
            seen = int(handle.read() or "0") + 1
            handle.seek(0)
            handle.write(str(seen))
    except FileNotFoundError:
        seen = 1
        with open(counter, "w", encoding="utf-8") as handle:
            handle.write("1")
    if store.processed(event["event_id"]):
        return
    if seen <= 1:
        store.mark_processed(event["event_id"])
        store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    else:
        store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""

# A handler that writes a flag three levels up from its cwd — into CrashCheck's scratch tree,
# beside the copied source. `check`'s settle() refuses it; `map` must degrade to that refusal.
WORLD_UP_FLAG = """import os


def apply_credit(store, event):
    world = os.path.basename(os.path.dirname(os.path.dirname(os.getcwd())))
    guard = os.path.join("..", "..", "..", world + ".inflight")
    if os.path.exists(guard):
        return
    with open(guard, "w", encoding="utf-8") as handle:
        handle.write(event["event_id"])
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
"""


def _port(tmp_path: Path, name: str, handler_source: str) -> Path:
    root = Path(str(tmp_path)) / name
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text('"""app"""\n', encoding="utf-8")
    (root / "app" / "credits.py").write_text(handler_source, encoding="utf-8")
    return root


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
    assert result.refusal is None
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
    assert result.refusal is not None
    assert "last page" in result.refusal
    assert result.windows == ()


def test_the_map_refuses_a_write_around_the_store_at_the_census() -> None:
    result = map_windows(f"fixture:{CREDIT}/raw-sql", CREDIT)
    assert result.mappable is True
    assert result.census_status == "INTEGRITY_ERROR"
    assert "wrote around the trusted store" in (result.refusal or "")
    assert result.windows == ()


def test_a_map_issues_no_verdict_and_writes_no_run_directory(_artifact_root: Path) -> None:
    result = map_windows(f"fixture:{INVENTORY}/atomic", INVENTORY)
    assert isinstance(result, MapResult)
    # MapResult carries no CrashVerdict field at all.
    assert "verdict" not in result.model_dump()
    # map_windows runs under its own temporary directory and keeps nothing under the artifact root.
    assert not (_artifact_root / "runs").exists()
    assert not (_artifact_root / "repros").exists()


def test_the_map_refuses_a_schedule_that_differs_between_worlds(tmp_path: Path) -> None:
    import uuid

    token = uuid.uuid4().hex
    counter = Path("/var/tmp") / f"nemisis-map-split-{token}"
    port = _port(tmp_path, "split", SPLIT_SCHEDULE.replace("__TOKEN__", token))
    try:
        result = map_windows(port, CREDIT)
    finally:
        counter.unlink(missing_ok=True)
    # check refuses this tree with _schedule_split; map must degrade the same way, not print a
    # clean window naming a commit a kill world never ran.
    assert result.mappable is True
    assert result.refusal is not None
    assert "commit schedule differs between worlds" in result.refusal
    assert result.windows == ()


def test_the_map_refuses_a_flag_written_into_the_scratch_tree(tmp_path: Path) -> None:
    port = _port(tmp_path, "world-up", WORLD_UP_FLAG)
    result = map_windows(port, CREDIT)
    # A write beside the copied source is caught by settle(), exactly as check catches it; the map
    # carries that refusal and no windows, never a clean map.
    assert result.mappable is True
    assert result.refusal is not None
    assert "scratch" in result.refusal
    assert result.windows == ()


def test_an_unbindable_tree_is_not_mappable(tmp_path: pytest.TempPathFactory) -> None:
    empty = Path(str(tmp_path)) / "no-handler"
    (empty / "app").mkdir(parents=True)
    (empty / "app" / "unrelated.py").write_text("x = 1\n", encoding="utf-8")
    result = map_windows(empty, CREDIT)
    assert result.mappable is False
    assert result.anchor_failure is not None
    assert result.tree_digest is None
    assert result.windows == ()
