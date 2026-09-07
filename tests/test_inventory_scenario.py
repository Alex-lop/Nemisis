"""``sqlite-inventory-v1``: the differential verifier's UNRESOLVED row, decided by CrashCheck.

Its own seed (stock 10, not 0), its own effect direction (a decrement), and its own predicate
(one reservation row, one marker, stock 8). Nothing here is a renamed credit.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

import nemisis.cli as cli
from nemisis.agent_patch import propose_patch
from nemisis.crash_fixture import load_event, load_issue, materialize_fixture
from nemisis.crash_models import CrashObservation, CrashVerdict, ExecutionStatus, WorldRole
from nemisis.crashcheck import CrashCheckError, accept_contract, check, initialize, replay
from nemisis.nemotron import NemotronClient, _Client
from nemisis.scenarios import SCENARIOS, scenario_for
from nemisis.scenarios.sqlite_inventory_v1 import INITIAL_ON_HAND
from nemisis.scenarios.sqlite_inventory_v1 import SCENARIO as INVENTORY

SCENARIO_ID = "sqlite-inventory-v1"
BUGGY = INVENTORY.ref("buggy")
GREEN = INVENTORY.ref("misleading-green")
ATOMIC = INVENTORY.ref("atomic")
MARK_FIRST = INVENTORY.ref("mark-first")
TARGET = "app.inventory:reserve_inventory"


def _tree(tmp_path: Path, name: str, handler_source: str) -> Path:
    root = tmp_path / name
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text('"""app"""\n', encoding="utf-8")
    (root / "app" / "inventory.py").write_text(handler_source, encoding="utf-8")
    return root


def test_registry_holds_both_scenarios_with_their_own_seed_direction_and_predicate() -> None:
    assert set(SCENARIOS) == {"sqlite-credit-v1", SCENARIO_ID}
    assert scenario_for(SCENARIO_ID) is INVENTORY
    event = load_event(INVENTORY)
    assert event == {"event_id": "order-1", "quantity": 2, "sku": "widget"}
    assert INVENTORY.initial_total(event) == INITIAL_ON_HAND == 10
    assert INVENTORY.effect_delta(event) == -2
    assert INVENTORY.repro_dir == "double-reservation"
    assert INVENTORY.target == TARGET
    assert "reserve_and_mark(sku, event_id, quantity)" in INVENTORY.store_remedy
    assert set(INVENTORY.store_operations) == {"reserve", "mark_reserved", "reserve_and_mark"}
    assert INVENTORY.format_subject(8) == "8 units"
    assert INVENTORY.format_subject(1) == "1 unit"
    assert "reserve_inventory" in load_issue(INVENTORY)


def test_the_hero_story_holds_for_a_decrement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Base reproduces, the agent's green rewrite still oversells, the atomic fix is proven."""
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(artifacts))

    result = check(BUGGY, GREEN, SCENARIO_ID, corrected=ATOMIC, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES, result.summary
    assert "double reservation (6 units on hand, expected 8 units)" in result.summary
    by_role = {
        role: {a.observation for a in result.attempts if a.role is role} for role in WorldRole
    }
    assert by_role[WorldRole.BASE] == {CrashObservation.DUPLICATE_EFFECT}
    assert by_role[WorldRole.CANDIDATE] == {CrashObservation.DUPLICATE_EFFECT}
    assert by_role[WorldRole.CORRECTED] == {CrashObservation.EXACTLY_ONCE}
    candidate = next(a for a in result.attempts if a.role is WorldRole.CANDIDATE)
    assert candidate.pre_crash_snapshot is not None
    assert candidate.pre_crash_snapshot.subject_total == 10
    assert candidate.checkpoint_snapshot is not None
    assert candidate.checkpoint_snapshot.subject_total == 8
    assert candidate.final_snapshot is not None
    assert (
        candidate.final_snapshot.subject_total,
        candidate.final_snapshot.event_effect_count,
        candidate.final_snapshot.event_effect_total,
    ) == (6, 2, -4)
    assert candidate.effect_delta == -2
    assert [sweep.role for sweep in result.sweeps] == [WorldRole.CORRECTED]
    assert result.sweeps[0].census.first_delivery_operations == ("reserve_and_mark",)
    assert result.artifacts["capsule"].startswith("repros/double-reservation/")
    capsule = json.loads((artifacts / result.artifacts["capsule"]).read_text(encoding="utf-8"))
    assert capsule["event"] == {"event_id": "order-1", "quantity": 2, "sku": "widget"}
    assert capsule["effect_delta"] == -2
    assert capsule["scenario_id"] == SCENARIO_ID
    report = (artifacts / result.artifacts["report"]).read_text(encoding="utf-8")
    assert "Expected stock after one delivery" in report
    assert "<strong>8 units</strong>" in report
    assert "<strong>6 units</strong>" in report
    assert "reservation rows 2 / marker 1" in report
    assert "$" not in report.split("<details")[0]
    assert cli._exit_code(result.verdict) == 1

    replayed = replay(artifacts / result.artifacts["capsule"], BUGGY, role="base")
    assert replayed.verdict is CrashVerdict.BUG_REPRODUCED
    proven = replay(artifacts / result.artifacts["capsule"], ATOMIC, role="corrected")
    assert proven.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    assert "exactly 8 units on hand, one reservation, and one marker" in proven.summary


def test_mark_first_loses_the_reservation_and_the_summary_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY, MARK_FIRST, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN, result.summary
    assert "commit 1 of 2 (mark_reserved)" in result.summary
    assert "10 units on hand instead of 8 units (0 reservation rows, 1 marker)" in result.summary
    assert "order is unfilled" in result.summary
    sweep = result.sweeps[0]
    assert sweep.census.first_delivery_operations == ("mark_reserved", "reserve")
    assert [a.observation for a in sweep.attempts] == [
        CrashObservation.INVARIANT_FAILED,
        CrashObservation.EXACTLY_ONCE,
    ]
    assert cli._exit_code(result.verdict) == 1


RAW_SQL_RESERVE = """import sqlite3


def reserve_inventory(store, event):
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute(
            "SELECT 1 FROM reserved_orders WHERE event_id = ?", (event["event_id"],)
        ).fetchone():
            connection.rollback()
            return
        connection.execute(
            "UPDATE stock SET on_hand = on_hand - ? WHERE sku = ?",
            (event["quantity"], event["sku"]),
        )
        connection.execute(
            "INSERT INTO reservations(event_id, sku, quantity) VALUES (?, ?, ?)",
            (event["event_id"], event["sku"], event["quantity"]),
        )
        connection.execute(
            "INSERT INTO reserved_orders(event_id) VALUES (?)", (event["event_id"],)
        )
        connection.commit()
"""

OTHER_SKU = """def reserve_inventory(store, event):
    store.reserve_and_mark("gadget", event["event_id"], event["quantity"])
"""


def test_raw_sql_and_look_alike_arguments_get_the_inventory_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    raw = check(BUGGY, _tree(tmp_path, "raw", RAW_SQL_RESERVE), SCENARIO_ID, mode="local")
    assert raw.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "without a single InventoryStore commit" in raw.summary
    assert "stock 8 units, 1 reservation row(s), 1 marker" in raw.summary
    assert "store.reserve_and_mark(sku, event_id, quantity)" in raw.summary
    assert "credit" not in raw.summary

    other = check(BUGGY, _tree(tmp_path, "other-sku", OTHER_SKU), SCENARIO_ID, mode="local")
    assert other.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert {a.execution_status for a in other.attempts if a.role is WorldRole.CANDIDATE} == {
        ExecutionStatus.CHECKPOINT_NOT_REACHED
    }
    assert "raised ValueError" in other.summary


def test_init_accept_and_check_bind_an_inventory_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    issue = workspace / "issue.md"
    issue.write_text(load_issue(INVENTORY) + "\nLocal contract.\n", encoding="utf-8")

    config = initialize(issue, TARGET, BUGGY, SCENARIO_ID)
    payload = json.loads(config.read_bytes())
    assert payload["status"] == "DRAFT" and payload["scenario_id"] == SCENARIO_ID
    contract = accept_contract(payload["contract"]["digest"], config)
    assert contract.scenario_id == SCENARIO_ID and contract.target == TARGET

    result = check(BUGGY, ATOMIC, config, mode="local")
    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE

    with pytest.raises(CrashCheckError, match="UNSUPPORTED_TARGET: unsupported scenario"):
        initialize(issue, TARGET, BUGGY, "sqlite-widgets-v9")
    with pytest.raises(CrashCheckError, match="pass --scenario sqlite-inventory-v1"):
        check(BUGGY, ATOMIC, "sqlite-credit-v1", mode="local")
    with pytest.raises(CrashCheckError, match="pass --scenario sqlite-inventory-v1"):
        initialize(issue, TARGET, BUGGY, "sqlite-credit-v1")


ATOMIC_INVENTORY_MODULE = '''"""Inventory reservation handler, fixed."""

from typing import Protocol, TypedDict


class ReservationEvent(TypedDict):
    event_id: str
    sku: str
    quantity: int


class InventoryStore(Protocol):
    def reserved(self, event_id: str) -> bool: ...

    def reserve(self, sku: str, event_id: str, quantity: int) -> None: ...

    def mark_reserved(self, event_id: str) -> None: ...

    def reserve_and_mark(self, sku: str, event_id: str, quantity: int) -> None: ...


def reserve_inventory(store: InventoryStore, event: ReservationEvent) -> None:
    store.reserve_and_mark(event["sku"], event["event_id"], event["quantity"])
'''


class _Models:
    def list(self, **kwargs: object) -> object:
        return {
            "data": [
                {
                    "id": "nvidia/nemotron-3-super-120b-a12b",
                    "status": "active",
                    "architecture": {"modality": "text->text"},
                    "supported_features": ["structured_outputs"],
                }
            ]
        }


class _Completions:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        payload = {
            "module_source": ATOMIC_INVENTORY_MODULE,
            "rationale": "Reserve and mark together.",
        }
        return {"choices": [{"message": {"content": json.dumps(payload), "refusal": None}}]}


class _FakeClient:
    def __init__(self) -> None:
        self.models = _Models()
        self.chat = type("Chat", (), {"completions": _Completions()})()


def test_propose_patch_hands_nemotron_the_inventory_store_api(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    issue = tmp_path / "issue.md"
    issue.write_text(load_issue(INVENTORY), encoding="utf-8")
    fake = _FakeClient()

    proposal = propose_patch(
        issue,
        BUGGY,
        tmp_path / "candidate",
        SCENARIO_ID,
        client=NemotronClient(client=cast(_Client, fake)),
    )

    messages = cast(list[dict[str, str]], fake.chat.completions.calls[0]["messages"])
    payload = json.loads(messages[1]["content"])
    assert "reserve_and_mark" in payload["storage_api"]
    assert "credit" not in payload["storage_api"]
    assert proposal.scenario_id == SCENARIO_ID
    result = check(BUGGY, tmp_path / "candidate", SCENARIO_ID, mode="local")
    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    assert result.candidate_author is not None


def test_cli_infers_the_scenario_from_a_fixture_base_and_names_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "check", "--base", BUGGY, "--candidate", GREEN, "--output-dir", str(tmp_path)],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    out = capsys.readouterr().out
    assert "verdict: PATCH_FAILED_STILL_REPRODUCES" in out
    assert "timeline: 8 units durable -> SIGKILL -> fresh worker -> 6 units" in out
    assert "$" not in out


def test_export_names_the_inventory_base_in_its_next_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "mine"
    monkeypatch.setattr(sys, "argv", ["nemisis", "export", GREEN, str(out)])

    cli.main()

    lines = capsys.readouterr().out.splitlines()
    assert lines[2] == f"edit: {out.resolve() / 'app' / 'inventory.py'}"
    assert lines[3].startswith(f"next: nemisis check --base {BUGGY} ")
    assert (
        materialize_fixture(BUGGY, tmp_path / "again").tree_digest
        == INVENTORY.tree_digests["buggy"]
    )


def test_inventory_unit_test_is_green_for_every_hero_tree(tmp_path: Path) -> None:
    for variant in INVENTORY.variants:
        tree = materialize_fixture(INVENTORY.ref(variant), tmp_path / variant).path
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
            cwd=tree,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert run.returncode == 0, run.stdout + run.stderr
        assert re.search(r"1 passed", run.stdout), run.stdout
