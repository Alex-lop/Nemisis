"""The scenario seam: the kernel reads one object, and the packaged contract agrees with it."""

from __future__ import annotations

import socket
import sqlite3
from pathlib import Path

import pytest

from nemisis.crash_fixture import FIXTURE_REFS, load_contract, load_event, materialize_fixture
from nemisis.crash_models import FaultBoundary
from nemisis.crashcheck import _ENGINE_RESOURCES
from nemisis.scenario import Scenario, StoreBase
from nemisis.scenarios import SCENARIOS, scenario_for
from nemisis.scenarios.sqlite_credit_v1 import SCENARIO as CREDIT
from nemisis.sqlite_runner import _ledger, _probe, _seed_database


def test_registry_holds_the_credit_scenario_and_refuses_the_rest() -> None:
    assert "sqlite-credit-v1" in SCENARIOS
    assert scenario_for("sqlite-credit-v1") is CREDIT
    with pytest.raises(
        ValueError, match="unsupported scenario: 'postgres-v9'; known: sqlite-credit-v1, "
    ):
        scenario_for("postgres-v9")
    with pytest.raises(ValueError, match="unsupported scenario"):
        scenario_for(None)


def test_packaged_contract_and_event_agree_with_the_scenario_object() -> None:
    contract = load_contract(CREDIT)
    assert contract["scenario_id"] == CREDIT.scenario_id
    assert contract["adapter_id"] == CREDIT.adapter_id
    assert contract["fault_intent_id"] == CREDIT.fault_intent_id
    assert contract["probe_id"] == CREDIT.probe_id
    assert contract["predicate_ids"] == [CREDIT.predicate_id]
    assert contract["event_fixture_id"] == CREDIT.event_fixture_id
    assert contract["target"] == CREDIT.target
    assert contract["originating_base_ref"] == CREDIT.buggy_ref
    event = load_event(CREDIT)
    assert set(event) == {"account_id", "amount_cents", "event_id"}
    assert CREDIT.effect_delta(event) == event["amount_cents"] == 2500
    assert CREDIT.ref("atomic") == "fixture:sqlite-credit-v1/atomic"
    assert CREDIT.variants == (*CREDIT.hero_variants, *CREDIT.zoo_variants)
    assert FIXTURE_REFS[: len(CREDIT.variants)] == tuple(CREDIT.ref(v) for v in CREDIT.variants)


def test_every_packaged_tree_digest_is_pinned_by_its_scenario(tmp_path: Path) -> None:
    for variant in CREDIT.variants:
        materialized = materialize_fixture(CREDIT.ref(variant), tmp_path / variant)
        assert materialized.tree_digest == CREDIT.tree_digests[variant]
        assert (materialized.path / CREDIT.handler_relative).is_file()


def test_store_operations_are_exactly_the_committing_store_methods() -> None:
    """Attribution can only explain operations it can model; every committing method must be
    listed, and nothing that does not commit may be. A committing method is one whose source
    reports its commit to the controller."""
    import inspect

    public = {
        name
        for name in vars(CREDIT.store_class)
        if not name.startswith("_") and callable(getattr(CREDIT.store_class, name))
    }
    committing = {
        name for name in public if "_pause(" in inspect.getsource(getattr(CREDIT.store_class, name))
    }
    assert (
        set(CREDIT.store_operations)
        == committing
        == {"credit", "mark_processed", "credit_and_mark"}
    )
    assert public - committing == {"processed"}
    assert issubclass(CREDIT.store_class, StoreBase)
    assert "store.credit_and_mark(account_id, event_id, amount_cents)" in CREDIT.store_remedy


def test_seed_probe_and_checkpoint_predicate_describe_the_same_database(tmp_path: Path) -> None:
    event = load_event(CREDIT)
    database = tmp_path / "seed.sqlite3"
    _seed_database(CREDIT, database, event)
    seeded = _probe(CREDIT, database, event)
    assert (
        seeded.subject_total,
        seeded.event_effect_count,
        seeded.event_effect_total,
        seeded.event_marker_count,
    ) == (0, 0, 0, 0)
    assert not CREDIT.checkpoint_reached(seeded, event, FaultBoundary.EFFECT_COMMIT)
    ledger = _ledger(CREDIT, database, event)
    for operation in CREDIT.store_operations:
        after = CREDIT.apply(ledger.content["tables"], operation, event)  # type: ignore[arg-type]
        predicted = CREDIT.snapshot(after, event)
        assert predicted.event_marker_count == (0 if operation == "credit" else 1)
        assert predicted.subject_total == (0 if operation == "mark_processed" else 2500)
    with pytest.raises(ValueError, match="unknown store operation"):
        CREDIT.apply(ledger.content["tables"], "transfer", event)  # type: ignore[arg-type]
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM accounts").fetchone() == (1,)


def test_store_base_requires_exact_types_and_reports_commits(tmp_path: Path) -> None:
    controller, worker = socket.socketpair()
    try:
        store = StoreBase(tmp_path / "unused.sqlite3", worker, {"event_id": "evt", "amount": 5})
        store._require(event_id="evt", amount=5)
        for bad in (
            {"event_id": b"evt"},
            {"amount": True},
            {"amount": 5.0},
            {"event_id": "other"},
            {"sku": "evt"},
        ):
            with pytest.raises(ValueError, match="outside the accepted contract"):
                store._require(**bad)
        controller.sendall(b'{"type":"continue"}\n')
        store._pause("credit")
        assert controller.recv(1024) == b'{"operation":"credit","sequence":1,"type":"commit"}\n'
    finally:
        controller.close()
        worker.close()


@pytest.mark.parametrize("scenario", list(SCENARIOS.values()), ids=lambda s: s.scenario_id)
def test_every_scenario_pins_its_trees_and_models_its_store(
    scenario: Scenario, tmp_path: Path
) -> None:
    """The invariants above hold for every registered scenario, not only the hero's."""
    import inspect

    for variant in scenario.variants:
        materialized = materialize_fixture(scenario.ref(variant), tmp_path / variant)
        assert materialized.tree_digest == scenario.tree_digests[variant]
    public = {
        name
        for name in vars(scenario.store_class)
        if not name.startswith("_") and callable(getattr(scenario.store_class, name))
    }
    committing = {
        name
        for name in public
        if "_pause(" in inspect.getsource(getattr(scenario.store_class, name))
    }
    assert set(scenario.store_operations) == committing
    event = load_event(scenario)
    database = tmp_path / "seed.sqlite3"
    _seed_database(scenario, database, event)
    ledger = _ledger(scenario, database, event)
    assert ledger.snapshot.subject_total == scenario.initial_total(event)
    assert (ledger.snapshot.event_effect_count, ledger.snapshot.event_marker_count) == (0, 0)
    for operation in scenario.store_operations:
        after = scenario.apply(ledger.content["tables"], operation, event)  # type: ignore[arg-type]
        predicted = scenario.snapshot(after, event)
        assert predicted.digest != ledger.snapshot.digest
    with pytest.raises(ValueError, match="unknown store operation"):
        scenario.apply(ledger.content["tables"], "transfer", event)  # type: ignore[arg-type]


def test_scenario_modules_are_trusted_engine_resources() -> None:
    import nemisis

    scenario_files = {
        f"scenarios/{path.name}"
        for path in (Path(nemisis.__file__).parent / "scenarios").glob("*.py")
    }
    assert scenario_files <= set(_ENGINE_RESOURCES)
    assert {"scenario.py", "display.py", "sqlite_runner.py"} <= set(_ENGINE_RESOURCES)
    assert isinstance(CREDIT, Scenario)
