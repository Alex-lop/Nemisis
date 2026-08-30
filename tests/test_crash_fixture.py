from __future__ import annotations

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

import nemisis.crash_fixture as crash_fixture
from nemisis.crash_fixture import (
    ATOMIC_REF,
    AUDITED_CONTRACT_DIGEST,
    BUGGY_REF,
    EVENT_DIGEST,
    FIXTURE_REFS,
    MISLEADING_GREEN_REF,
    FixtureEvent,
    load_contract,
    load_event,
    load_event_bytes,
    load_issue,
    materialize_fixture,
)
from nemisis.hashing import sha256_json, sha256_text, sha256_tree


class MemoryStore:
    def __init__(self) -> None:
        self.balance_cents = 0
        self.processed_events: set[str] = set()

    def processed(self, event_id: str) -> bool:
        return event_id in self.processed_events

    def credit(self, account_id: str, event_id: str, amount_cents: int) -> None:
        self.balance_cents += amount_cents

    def mark_processed(self, event_id: str) -> None:
        self.processed_events.add(event_id)

    def credit_and_mark(self, account_id: str, event_id: str, amount_cents: int) -> None:
        if not self.processed(event_id):
            self.credit(account_id, event_id, amount_cents)
            self.mark_processed(event_id)


def test_audited_contract_issue_and_event_are_exactly_bound() -> None:
    contract = load_contract()
    event = load_event()

    assert sha256_json(contract) == AUDITED_CONTRACT_DIGEST
    assert sha256_text(load_issue()) == contract["issue_digest"]
    assert sha256_json(event) == EVENT_DIGEST == contract["event_digest"]
    assert load_event_bytes() == (
        b'{"account_id":"acct_7","amount_cents":2500,"event_id":"evt_1042"}'
    )
    assert contract["originating_base_ref"] == BUGGY_REF


@pytest.mark.parametrize(
    ("ref", "expected_balance"),
    [
        (BUGGY_REF, 2500),
        (MISLEADING_GREEN_REF, 2500),
        (ATOMIC_REF, 2500),
    ],
)
def test_materializes_exact_tree_and_preserves_expected_duplicate_behavior(
    tmp_path: Path, ref: str, expected_balance: int
) -> None:
    result = materialize_fixture(ref, tmp_path / "tree")

    assert result.ref == ref
    assert result.path == (tmp_path / "tree").resolve()
    assert result.tree_digest == sha256_tree(result.path)
    assert {
        path.relative_to(result.path).as_posix()
        for path in result.path.rglob("*")
        if path.is_file()
    } == {"app/__init__.py", "app/credits.py", "tests/test_credits.py"}

    handler = cast(
        Callable[[MemoryStore, FixtureEvent], None],
        runpy.run_path(str(result.path / "app/credits.py"))["apply_credit"],
    )
    store = MemoryStore()
    event = load_event()
    handler(store, event)
    handler(store, event)
    assert store.balance_cents == expected_balance


def test_rejects_unknown_refs_before_creating_a_destination(tmp_path: Path) -> None:
    destination = tmp_path / "tree"
    with pytest.raises(ValueError, match="unknown fixture ref"):
        materialize_fixture("fixture:sqlite-credit-v1/unknown", destination)
    assert not destination.exists()
    assert FIXTURE_REFS == (BUGGY_REF, MISLEADING_GREEN_REF, ATOMIC_REF)


def test_rejects_a_changed_packaged_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = crash_fixture._resource_bytes

    def changed_contract(relative: str) -> bytes:
        return b"{}" if relative == "contract.json" else original(relative)

    monkeypatch.setattr(crash_fixture, "_resource_bytes", changed_contract)
    with pytest.raises(ValueError, match="contract bytes changed"):
        load_contract()
