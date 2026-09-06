"""``sqlite-inventory-v1``: one stock reservation, doubled by a crash between decrement and marker.

This is the bug the original differential verifier's ``idempotency-retry`` fixture could only
mark ``UNRESOLVED``: an order reserves two units of a SKU, the worker dies after the decrement is
durable, the retry decrements again, and the shelf reads two units short of the truth. The effect
runs the other way from the credit scenario (the subject goes down), the seed is not zero, and
exactly once means the stock landed on 8 from 10 with one reservation row and one marker.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from nemisis.crash_models import CrashVerdict, FaultBoundary, StateSnapshot
from nemisis.hashing import sha256_json
from nemisis.scenario import Event, Scenario, StoreBase, connect

SCENARIO_ID = "sqlite-inventory-v1"
INITIAL_ON_HAND = 10
SCHEMA = """
CREATE TABLE stock(
    sku TEXT PRIMARY KEY,
    on_hand INTEGER NOT NULL
);
CREATE TABLE reservations(
    id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL
);
CREATE TABLE reserved_orders(event_id TEXT PRIMARY KEY);
"""

ISSUE_DIGEST = "9348080afa767b7ea96370dd910e43374a1163e3d7a62a3186e27daf42bbe145"
EVENT_DIGEST = "f476dc612df218114e0073a77fd6a0bd00d4595ea6efb75bccfd8aea440bd0c9"
EVENT_RESOURCE_DIGEST = "f476dc612df218114e0073a77fd6a0bd00d4595ea6efb75bccfd8aea440bd0c9"
AUDITED_CONTRACT_DIGEST = "09e11ea1b0a3100872455acd2957e68c83b9072aff4fbea130a05adf9abe3a66"
CONTRACT_RESOURCE_DIGEST = "0ebdbd111ae79e79fe899a8ed59585b1f463e3e69f31d7aa510464e4fe5c871c"
HERO_VARIANTS = ("buggy", "misleading-green", "atomic")
ZOO_VARIANTS = ("mark-first",)
TREE_DIGESTS: Mapping[str, str] = {
    "buggy": "b7203d3b948d95e5f829839f791fc63e0ce2a9aca0f08a75351d536ac86859a7",
    "misleading-green": "17718b6e986ca13ad288ddba99df9155be751d8e98be247af78761156c173edf",
    "atomic": "29c9b37f10a2513616c5bc6f4054df59b0759fdf426ea67151ff75774db803c3",
    "mark-first": "e886fae6880a3e0294a04763f9486bd4c1c801fa9ad7438f6ea0b80d7a276147",
}

STORE_REMEDY = (
    "Kill points are store commits, so a write the store did not make has no kill point and "
    "earns no verdict. Express the same fix through the store: store.reserve_and_mark(sku, "
    "event_id, quantity) commits the decrement, the reservation row, and its marker together in "
    "one durable transaction; store.reserved(event_id), store.reserve(...), and "
    "store.mark_reserved(event_id) are the three-step form; see docs/PRODUCT.md#the-store-api"
)
STORE_API_FALLBACK = (
    "store.reserved(event_id) -> bool; store.reserve(sku, event_id, quantity); "
    "store.mark_reserved(event_id); store.reserve_and_mark(sku, event_id, quantity). Every call "
    "is one durable SQLite commit."
)


class InventoryStore(StoreBase):
    """Fixed trusted store exposed to the candidate handler."""

    def reserved(self, event_id: str) -> bool:
        self._require(event_id=event_id)
        with connect(self._database) as connection:
            row = connection.execute(
                "SELECT 1 FROM reserved_orders WHERE event_id = ?", (event_id,)
            ).fetchone()
        return row is not None

    def reserve(self, sku: str, event_id: str, quantity: int) -> None:
        self._require(sku=sku, event_id=event_id, quantity=quantity)
        with connect(self._database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE stock SET on_hand = on_hand - ? WHERE sku = ?", (quantity, sku)
            )
            connection.execute(
                "INSERT INTO reservations(event_id, sku, quantity) VALUES (?, ?, ?)",
                (event_id, sku, quantity),
            )
            connection.commit()
        self._pause("reserve")

    def mark_reserved(self, event_id: str) -> None:
        self._require(event_id=event_id)
        with connect(self._database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO reserved_orders(event_id) VALUES (?)", (event_id,))
            connection.commit()
        self._pause("mark_reserved")

    def reserve_and_mark(self, sku: str, event_id: str, quantity: int) -> None:
        self._require(sku=sku, event_id=event_id, quantity=quantity)
        with connect(self._database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM reserved_orders WHERE event_id = ?", (event_id,)
            ).fetchone():
                connection.rollback()
                return
            connection.execute(
                "UPDATE stock SET on_hand = on_hand - ? WHERE sku = ?", (quantity, sku)
            )
            connection.execute(
                "INSERT INTO reservations(event_id, sku, quantity) VALUES (?, ?, ?)",
                (event_id, sku, quantity),
            )
            connection.execute("INSERT INTO reserved_orders(event_id) VALUES (?)", (event_id,))
            connection.commit()
        self._pause("reserve_and_mark")


# What each trusted store operation may change: (on hand, reservation rows, signed change, marker).
STORE_OPERATIONS: Mapping[str, Any] = {
    "reserve": lambda event: (-event["quantity"], 1, -event["quantity"], 0),
    "mark_reserved": lambda event: (0, 0, 0, 1),
    "reserve_and_mark": lambda event: (-event["quantity"], 1, -event["quantity"], 1),
}


def normalize_event(value: object) -> Event:
    if not isinstance(value, Mapping) or set(value) != {"event_id", "quantity", "sku"}:
        raise ValueError("event must contain exactly event_id, quantity, and sku")
    event_id, quantity, sku = value["event_id"], value["quantity"], value["sku"]
    if (
        not isinstance(event_id, str)
        or not event_id
        or type(quantity) is not int
        or quantity <= 0
        or quantity > INITIAL_ON_HAND
        or not isinstance(sku, str)
        or not sku
    ):
        raise ValueError("event fields are invalid")
    return {"event_id": event_id, "quantity": quantity, "sku": sku}


def seed_identity(event: Event) -> dict[str, object]:
    return {
        "journal_mode": "WAL",
        "schema": SCHEMA,
        "schema_version": "1",
        "stock": {"on_hand": INITIAL_ON_HAND, "sku": event["sku"]},
        "synchronous": "FULL",
    }


def seed(connection: sqlite3.Connection, event: Event) -> None:
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT INTO stock(sku, on_hand) VALUES (?, ?)", (event["sku"], INITIAL_ON_HAND)
    )


def probe(connection: sqlite3.Connection, event: Event) -> StateSnapshot:
    stock = connection.execute(
        "SELECT on_hand FROM stock WHERE sku = ?", (event["sku"],)
    ).fetchone()
    rows = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM reservations WHERE event_id = ?",
        (event["event_id"],),
    ).fetchone()
    marker = connection.execute(
        "SELECT COUNT(*) FROM reserved_orders WHERE event_id = ?", (event["event_id"],)
    ).fetchone()
    if stock is None or rows is None or marker is None:
        raise sqlite3.OperationalError("read-only state probe was incomplete")
    return StateSnapshot.with_digest(
        subject_total=int(stock[0]),
        event_effect_count=int(rows[0]),
        event_effect_total=-int(rows[1]),
        event_marker_count=int(marker[0]),
    )


def others(connection: sqlite3.Connection, event: Event) -> dict[str, list[list[object]]]:
    rows = {
        "stock": connection.execute(
            "SELECT sku, on_hand FROM stock WHERE sku IS NOT ? ORDER BY sku", (event["sku"],)
        ).fetchall(),
        "reservations": connection.execute(
            "SELECT id, event_id, sku, quantity FROM reservations WHERE event_id IS NOT ? "
            "ORDER BY id",
            (event["event_id"],),
        ).fetchall(),
        "reserved_orders": connection.execute(
            "SELECT event_id FROM reserved_orders WHERE event_id IS NOT ? ORDER BY event_id",
            (event["event_id"],),
        ).fetchall(),
    }
    return {name: [list(row) for row in table] for name, table in rows.items()}


SEEDED_OTHERS_DIGEST = sha256_json({"reservations": [], "reserved_orders": [], "stock": []})


def effect_delta(event: Event) -> int:
    quantity = event["quantity"]
    assert isinstance(quantity, int)
    return -quantity


def initial_total(event: Event) -> int:
    return INITIAL_ON_HAND


def checkpoint_reached(snapshot: StateSnapshot, event: Event, boundary: FaultBoundary) -> bool:
    """The capsule's kill point: one durable decrement, plus its marker at the marker boundary."""
    delta = effect_delta(event)
    return (
        snapshot.subject_total == INITIAL_ON_HAND + delta
        and snapshot.event_effect_count == 1
        and snapshot.event_effect_total == delta
        and (boundary is FaultBoundary.EFFECT_COMMIT or snapshot.event_marker_count == 1)
    )


def format_subject(on_hand: int) -> str:
    return f"{on_hand} unit{'' if on_hand == 1 else 's'}"


def describe_final(final: StateSnapshot, event: Event) -> str:
    event_id = event["event_id"]
    expected = INITIAL_ON_HAND + effect_delta(event)
    rows = (
        f"{final.event_effect_count} reservation row{'s' if final.event_effect_count != 1 else ''}"
    )
    marker = f"{final.event_marker_count} marker"
    if final.event_effect_count == 0 and final.event_marker_count == 1:
        cause = f"{event_id} was marked reserved but nothing was reserved, so the order is unfilled"
    elif final.event_effect_count == 2:
        cause = f"{event_id} was reserved twice"
    elif final.event_effect_count > 2:
        cause = f"{event_id} was reserved {final.event_effect_count} times"
    else:
        cause = "the final state matches neither exactly-once nor the capsule's duplicate shape"
    return (
        f"{format_subject(final.subject_total)} on hand instead of {format_subject(expected)} "
        f"({rows}, {marker}): {cause}"
    )


def verdict_summary(verdict: CrashVerdict, event: Event) -> str:
    event_id, quantity = event["event_id"], event["quantity"]
    assert isinstance(quantity, int)
    once = format_subject(INITIAL_ON_HAND - quantity)
    twice = format_subject(INITIAL_ON_HAND - 2 * quantity)
    return {
        CrashVerdict.BUG_REPRODUCED: (
            f"The base replayed {event_id} to a durable double reservation ({twice} on hand, "
            f"expected {once})."
        ),
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES: (
            f"The candidate replayed {event_id} to a durable double reservation ({twice} on "
            f"hand, expected {once})."
        ),
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN: (
            "The candidate completed every world in a state that is neither exactly-once nor "
            "the capsule's duplicate."
        ),
        CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE: (
            f"Five fresh worlds ended at exactly {once} on hand, one reservation, and one marker."
        ),
        CrashVerdict.EVIDENCE_INCOMPLETE: "Required crash evidence was incomplete.",
        CrashVerdict.UNSUPPORTED_TARGET: "The supplied target is unsupported.",
    }[verdict]


SCENARIO = Scenario(
    scenario_id=SCENARIO_ID,
    adapter_id="inventory-store-v1",
    fault_intent_id="first-reservation-effect-commit-v1",
    probe_id="stock-state-v1",
    predicate_id="single-reservation-and-marker-v1",
    event_fixture_id="order-1-v1",
    target="app.inventory:reserve_inventory",
    fixture_package="sqlite_inventory_v1",
    handler_relative="app/inventory.py",
    common_files=(
        ("common/app/__init__.py", "app/__init__.py"),
        ("common/tests/test_inventory.py", "tests/test_inventory.py"),
    ),
    hero_variants=HERO_VARIANTS,
    zoo_variants=ZOO_VARIANTS,
    tree_digests=TREE_DIGESTS,
    issue_digest=ISSUE_DIGEST,
    event_digest=EVENT_DIGEST,
    event_resource_digest=EVENT_RESOURCE_DIGEST,
    audited_contract_digest=AUDITED_CONTRACT_DIGEST,
    contract_resource_digest=CONTRACT_RESOURCE_DIGEST,
    repro_dir="double-reservation",
    schema=SCHEMA,
    seed_identity=seed_identity,
    seed=seed,
    probe=probe,
    others=others,
    seeded_others_digest=SEEDED_OTHERS_DIGEST,
    store_class=InventoryStore,
    store_operations=STORE_OPERATIONS,
    store_remedy=STORE_REMEDY,
    store_api_fallback=STORE_API_FALLBACK,
    normalize_event=normalize_event,
    effect_delta=effect_delta,
    initial_total=initial_total,
    checkpoint_reached=checkpoint_reached,
    scalar_name="quantity",
    scalar_bounds=(1, INITIAL_ON_HAND),
    subject_noun="stock",
    effect_noun="reservation",
    effect_verb="reserves",
    others_noun="other SKUs or orders",
    format_subject=format_subject,
    describe_final=describe_final,
    verdict_summary=verdict_summary,
)

__all__ = [
    "AUDITED_CONTRACT_DIGEST",
    "CONTRACT_RESOURCE_DIGEST",
    "EVENT_DIGEST",
    "EVENT_RESOURCE_DIGEST",
    "HERO_VARIANTS",
    "INITIAL_ON_HAND",
    "ISSUE_DIGEST",
    "SCENARIO",
    "SCENARIO_ID",
    "SCHEMA",
    "STORE_OPERATIONS",
    "STORE_REMEDY",
    "TREE_DIGESTS",
    "ZOO_VARIANTS",
    "InventoryStore",
]
