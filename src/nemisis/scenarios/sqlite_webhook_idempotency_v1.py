"""``sqlite-webhook-idempotency-v1``: one Stripe-shaped webhook, granted twice by a crash.

A payment provider redelivers ``checkout.session.completed`` whenever the endpoint does not answer
in time, and the endpoint is expected to be idempotent on the event id. The handler grants the
purchased seats and then writes the idempotency key; a crash in that window leaves the grant
durable and the key missing, so the redelivery grants the seats again and the workspace bills for
seats nobody bought. The seed is not empty (the founder already holds one seat) and the effect runs
upward, so exactly once means four seats from one, with one grant row and one key.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from nemisis.crash_models import CrashVerdict, FaultBoundary, StateSnapshot
from nemisis.scenario import Event, Scenario, StoreBase, Tables

SCENARIO_ID = "sqlite-webhook-idempotency-v1"
INITIAL_SEATS = 1
MAX_SEATS = 1_000
SCHEMA = """
CREATE TABLE workspaces(
    workspace_id TEXT PRIMARY KEY,
    seats INTEGER NOT NULL
);
CREATE TABLE seat_grants(
    id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    seats INTEGER NOT NULL
);
CREATE TABLE delivered_webhooks(event_id TEXT PRIMARY KEY);
"""

ISSUE_DIGEST = "a87a2a71c58fd821753911a8207a474d83aed92bfd6284344e5927b498247ce6"
EVENT_DIGEST = "020ff03bf30b0e5d573ebad8ad41c532cecb13a28e55c0ccd7235ed73a7e4337"
EVENT_RESOURCE_DIGEST = "020ff03bf30b0e5d573ebad8ad41c532cecb13a28e55c0ccd7235ed73a7e4337"
AUDITED_CONTRACT_DIGEST = "460fc56cbbc6ee84770ff21ccd2f29e17f4c0de8ac4c0c512b8c5e21324dad57"
CONTRACT_RESOURCE_DIGEST = "d88b56e554e36e23e5794d1d445f4e7ebb133758cea65cfb35af0374d37b2bf9"
HERO_VARIANTS = ("buggy", "misleading-green", "atomic")
# The zoo the sweep and the attribution need: the reordering that loses the grant, and the two
# shapes that keep their durable state where no kill point can reach it.
ZOO_VARIANTS = ("mark-first", "raw-sql", "shadow-table")
TREE_DIGESTS: Mapping[str, str] = {
    "buggy": "982b7f581adb8601dd244c2bd5662f2c031fe8aafa7832eff37cf7c9db144f0e",
    "misleading-green": "44f788c899b8db548e97fab7a91bc3b336cfe19735790b28b57370efb57e0994",
    "atomic": "272334fe3daf5f8b66fe5db1592e0e68dd801148dc40c85f7e69c31ab6c369bc",
    "mark-first": "0e5874e130b7c7227c0e37c4ac1a4debda28fc62dafe4d3cfdd28a3c1b6beab3",
    "raw-sql": "75aedc362a89f3b7f8ec98025b9c00635eb868b413348d34dbdab954590ef2ef",
    "shadow-table": "924e05e3ff93e6984e4b8c6982711b38c4a80e7c083797251cca33e64274aded",
}

STORE_REMEDY = (
    "Kill points are store commits, so a write the store did not make has no kill point and "
    "earns no verdict. Express the same fix through the store: store.grant_and_mark(workspace_id, "
    "event_id, seats) commits the seat grant and its idempotency key together in one durable "
    "transaction; store.processed(event_id), store.grant(...), and store.mark_processed(event_id) "
    "are the three-step form; see docs/PRODUCT.md#the-store-api"
)
STORE_API_FALLBACK = (
    "store.processed(event_id) -> bool; store.grant(workspace_id, event_id, seats); "
    "store.mark_processed(event_id); store.grant_and_mark(workspace_id, event_id, seats). Every "
    "call is one durable SQLite commit."
)


class WebhookStore(StoreBase):
    """Fixed trusted store exposed to the candidate handler."""

    def processed(self, event_id: str) -> bool:
        self._require(event_id=event_id)
        with self._connection as connection:
            row = connection.execute(
                "SELECT 1 FROM delivered_webhooks WHERE event_id = ?", (event_id,)
            ).fetchone()
        self._settle()
        return row is not None

    def grant(self, workspace_id: str, event_id: str, seats: int) -> None:
        self._require(workspace_id=workspace_id, event_id=event_id, seats=seats)
        with self._connection as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE workspaces SET seats = seats + ? WHERE workspace_id = ?",
                (seats, workspace_id),
            )
            connection.execute(
                "INSERT INTO seat_grants(event_id, workspace_id, seats) VALUES (?, ?, ?)",
                (event_id, workspace_id, seats),
            )
            connection.commit()
        self._pause("grant")

    def mark_processed(self, event_id: str) -> None:
        self._require(event_id=event_id)
        with self._connection as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO delivered_webhooks(event_id) VALUES (?)", (event_id,))
            connection.commit()
        self._pause("mark_processed")

    def grant_and_mark(self, workspace_id: str, event_id: str, seats: int) -> None:
        self._require(workspace_id=workspace_id, event_id=event_id, seats=seats)
        with self._connection as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM delivered_webhooks WHERE event_id = ?", (event_id,)
            ).fetchone():
                connection.rollback()
                return
            connection.execute(
                "UPDATE workspaces SET seats = seats + ? WHERE workspace_id = ?",
                (seats, workspace_id),
            )
            connection.execute(
                "INSERT INTO seat_grants(event_id, workspace_id, seats) VALUES (?, ?, ?)",
                (event_id, workspace_id, seats),
            )
            connection.execute("INSERT INTO delivered_webhooks(event_id) VALUES (?)", (event_id,))
            connection.commit()
        self._pause("grant_and_mark")


STORE_OPERATIONS = ("grant", "mark_processed", "grant_and_mark")


def _next_rowid(rows: list[list[object]]) -> int:
    """SQLite's next rowid for a table nothing ever deletes from: one past the largest."""
    return max((row[0] for row in rows if isinstance(row[0], int)), default=0) + 1


def normalize_event(value: object) -> Event:
    if not isinstance(value, Mapping) or set(value) != {"event_id", "seats", "workspace_id"}:
        raise ValueError("event must contain exactly event_id, seats, and workspace_id")
    event_id, seats, workspace_id = value["event_id"], value["seats"], value["workspace_id"]
    if (
        not isinstance(event_id, str)
        or not event_id
        or type(seats) is not int
        or seats <= 0
        or seats > MAX_SEATS
        or not isinstance(workspace_id, str)
        or not workspace_id
    ):
        raise ValueError("event fields are invalid")
    return {"event_id": event_id, "seats": seats, "workspace_id": workspace_id}


def seed_identity(event: Event) -> dict[str, object]:
    return {
        "journal_mode": "WAL",
        "schema": SCHEMA,
        "schema_version": "1",
        "synchronous": "FULL",
        "workspace": {"seats": INITIAL_SEATS, "workspace_id": event["workspace_id"]},
    }


def seed(connection: sqlite3.Connection, event: Event) -> None:
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT INTO workspaces(workspace_id, seats) VALUES (?, ?)",
        (event["workspace_id"], INITIAL_SEATS),
    )


def tables(connection: sqlite3.Connection) -> Tables:
    """Every row of every seeded table, in canonical order; grants keep insertion order."""
    return {
        "workspaces": [
            list(row)
            for row in connection.execute(
                "SELECT rowid, workspace_id, seats FROM workspaces ORDER BY workspace_id"
            )
        ],
        "seat_grants": [
            list(row)
            for row in connection.execute(
                "SELECT id, event_id, workspace_id, seats FROM seat_grants ORDER BY id"
            )
        ],
        "delivered_webhooks": [
            list(row)
            for row in connection.execute(
                "SELECT rowid, event_id FROM delivered_webhooks ORDER BY event_id"
            )
        ],
    }


def snapshot(rows: Tables, event: Event) -> StateSnapshot:
    """The four numbers a receipt carries; the effect total is the signed seat change."""
    seats = next(
        (row[2] for row in rows["workspaces"] if row[1] == event["workspace_id"]),
        None,
    )
    if not isinstance(seats, int):
        raise ValueError("the event's workspace row is missing")
    grants = [row for row in rows["seat_grants"] if row[1] == event["event_id"]]
    total = sum(row[3] for row in grants if isinstance(row[3], int))
    marker = sum(1 for row in rows["delivered_webhooks"] if row[1] == event["event_id"])
    return StateSnapshot.with_digest(
        subject_total=seats,
        event_effect_count=len(grants),
        event_effect_total=total,
        event_marker_count=marker,
    )


def apply(rows: Tables, operation: str, event: Event) -> Tables:
    """What the database must hold after the named store commit, and nothing else."""
    workspace_id, event_id, seats = event["workspace_id"], event["event_id"], event["seats"]
    after: Tables = {name: [list(row) for row in table] for name, table in rows.items()}
    if operation in {"grant", "grant_and_mark"}:
        for row in after["workspaces"]:
            if row[1] == workspace_id and isinstance(row[2], int) and isinstance(seats, int):
                row[2] = row[2] + seats
        after["seat_grants"].append(
            [_next_rowid(after["seat_grants"]), event_id, workspace_id, seats]
        )
    if operation in {"mark_processed", "grant_and_mark"}:
        after["delivered_webhooks"] = sorted(
            [*after["delivered_webhooks"], [_next_rowid(after["delivered_webhooks"]), event_id]],
            key=lambda row: str(row[1]),
        )
    if operation not in STORE_OPERATIONS:
        raise ValueError(f"unknown store operation {operation!r}")
    return after


def effect_delta(event: Event) -> int:
    seats = event["seats"]
    assert isinstance(seats, int)
    return seats


def initial_total(event: Event) -> int:
    return INITIAL_SEATS


def checkpoint_reached(snapshot: StateSnapshot, event: Event, boundary: FaultBoundary) -> bool:
    """The capsule's kill point: one durable grant, plus its key at the marker boundary."""
    delta = effect_delta(event)
    return (
        snapshot.subject_total == INITIAL_SEATS + delta
        and snapshot.event_effect_count == 1
        and snapshot.event_effect_total == delta
        and (boundary is FaultBoundary.EFFECT_COMMIT or snapshot.event_marker_count == 1)
    )


def format_subject(seats: int) -> str:
    return f"{seats} seat{'' if seats == 1 else 's'}"


def describe_final(final: StateSnapshot, event: Event) -> str:
    event_id = event["event_id"]
    expected = INITIAL_SEATS + effect_delta(event)
    rows = f"{final.event_effect_count} grant row{'s' if final.event_effect_count != 1 else ''}"
    marker = f"{final.event_marker_count} idempotency key"
    if final.event_effect_count == 0 and final.event_marker_count == 1:
        cause = (
            f"{event_id} was keyed as delivered but no seats were granted, so the purchase is lost"
        )
    elif final.event_effect_count == 1 and final.event_marker_count == 0:
        cause = f"{event_id} was granted but never keyed, so the next redelivery grants it again"
    elif final.event_effect_count == 2:
        cause = f"{event_id} was granted twice"
    elif final.event_effect_count > 2:
        cause = f"{event_id} was granted {final.event_effect_count} times"
    else:
        cause = "the final state matches neither exactly-once nor the capsule's duplicate shape"
    return (
        f"{format_subject(final.subject_total)} instead of {format_subject(expected)} "
        f"({rows}, {marker}): {cause}"
    )


def verdict_summary(verdict: CrashVerdict, event: Event) -> str:
    event_id, seats = event["event_id"], effect_delta(event)
    once = format_subject(INITIAL_SEATS + seats)
    twice = format_subject(INITIAL_SEATS + 2 * seats)
    return {
        CrashVerdict.BUG_REPRODUCED: (
            f"The base replayed {event_id} to a durable double grant ({twice}, expected {once})."
        ),
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES: (
            f"The candidate replayed {event_id} to a durable double grant ({twice}, expected "
            f"{once})."
        ),
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN: (
            "The candidate completed every world in a state that is neither exactly-once nor "
            "the capsule's duplicate."
        ),
        CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE: (
            f"Five fresh worlds ended at exactly {once}, one grant, and one idempotency key."
        ),
        CrashVerdict.EVIDENCE_INCOMPLETE: "Required crash evidence was incomplete.",
        CrashVerdict.UNSUPPORTED_TARGET: "The supplied target is unsupported.",
    }[verdict]


SCENARIO = Scenario(
    scenario_id=SCENARIO_ID,
    adapter_id="webhook-store-v1",
    fault_intent_id="first-grant-effect-commit-v1",
    probe_id="seat-state-v1",
    predicate_id="single-grant-and-key-v1",
    event_fixture_id="evt-whk-88-v1",
    target="app.webhooks:handle_webhook",
    fixture_package="sqlite_webhook_idempotency_v1",
    handler_relative="app/webhooks.py",
    common_files=(
        ("common/app/__init__.py", "app/__init__.py"),
        ("common/tests/test_webhooks.py", "tests/test_webhooks.py"),
    ),
    hero_variants=HERO_VARIANTS,
    zoo_variants=ZOO_VARIANTS,
    tree_digests=TREE_DIGESTS,
    issue_digest=ISSUE_DIGEST,
    event_digest=EVENT_DIGEST,
    event_resource_digest=EVENT_RESOURCE_DIGEST,
    audited_contract_digest=AUDITED_CONTRACT_DIGEST,
    contract_resource_digest=CONTRACT_RESOURCE_DIGEST,
    repro_dir="double-grant",
    schema=SCHEMA,
    seed_identity=seed_identity,
    seed=seed,
    tables=tables,
    snapshot=snapshot,
    apply=apply,
    store_operations=STORE_OPERATIONS,
    store_class=WebhookStore,
    store_remedy=STORE_REMEDY,
    store_api_fallback=STORE_API_FALLBACK,
    normalize_event=normalize_event,
    effect_delta=effect_delta,
    initial_total=initial_total,
    checkpoint_reached=checkpoint_reached,
    scalar_name="seats",
    scalar_bounds=(1, MAX_SEATS),
    subject_noun="seat count",
    effect_noun="grant",
    effect_verb="grants",
    others_noun="other workspaces or webhook events",
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
    "INITIAL_SEATS",
    "ISSUE_DIGEST",
    "MAX_SEATS",
    "SCENARIO",
    "SCENARIO_ID",
    "SCHEMA",
    "STORE_OPERATIONS",
    "STORE_REMEDY",
    "TREE_DIGESTS",
    "ZOO_VARIANTS",
    "WebhookStore",
]
