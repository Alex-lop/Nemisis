"""``sqlite-outbox-v1``: one outbox send, doubled by a crash between the row and its marker.

A transactional outbox is the standard answer to "send exactly once": write the row that stands
for the email or the webhook in the same durable transaction as the marker that says it was sent.
The bug is what happens when those are two transactions. The worker writes the outbox row, dies
before the marker, and the retry writes the row again: the customer is notified twice and the
channel shows twice the payload it was handed. Nothing here is a renamed credit -- the subject is
bytes handed to one channel, the effect row is an outbox row, and the marker is a send receipt.

What the receipt proves is the row, never the email: a handler that calls SMTP twice and writes
one outbox row reads exactly once here. That is the same contract the credit ledger row makes,
and it is stated rather than implied (``docs/DECISIONS.md``, "What a third scenario would need
the seam to say"). The other caveat that decision named -- that an outbox event has no natural
integer for ``scalar_name`` -- is answered by the payload: bytes handed to the channel are the
subject, one send moves them by the message's own size, and the seam needed no widening.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from nemisis.crash_models import CrashVerdict, FaultBoundary, StateSnapshot
from nemisis.scenario import Event, Scenario, StoreBase, Tables

SCENARIO_ID = "sqlite-outbox-v1"
INITIAL_SENT_BYTES = 0
MAX_PAYLOAD_BYTES = 1_000_000
SCHEMA = """
CREATE TABLE channels(
    channel TEXT PRIMARY KEY,
    sent_bytes INTEGER NOT NULL
);
CREATE TABLE outbox(
    id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    payload_bytes INTEGER NOT NULL
);
CREATE TABLE sent_events(event_id TEXT PRIMARY KEY);
"""

ISSUE_DIGEST = "34b21d9c2cf9e0f2362000d584185c1692d9079ce20138aa93056224394bff6e"
EVENT_DIGEST = "d068de76d1045815954ad7c56097a6ff0a487764eaeb4ec045dff51925997410"
EVENT_RESOURCE_DIGEST = "d068de76d1045815954ad7c56097a6ff0a487764eaeb4ec045dff51925997410"
AUDITED_CONTRACT_DIGEST = "5f60e941dbe364d7cd6a5867807e4ec37070410db2cd66cb461f514f955fb1af"
CONTRACT_RESOURCE_DIGEST = "8796e42ce52730ceb6be956f1c6fd419e9dc550f72cf612a9a1e4d388c803d46"
# The three-tree hero, in canonical order, then the candidate zoo: the same six shapes the credit
# scenario keeps, spelled for a send. Each one is a patch a reviewer would sign off on.
HERO_VARIANTS = ("buggy", "misleading-green", "atomic")
ZOO_VARIANTS = (
    "mark-first",
    "leftover-send",
    "never-marks",
    "raw-sql",
    "shadow-table",
    "tail-bytes",
)
TREE_DIGESTS: Mapping[str, str] = {
    "buggy": "9e1810d97379db3acfc750958364058da13db41cb1916fa13dc43eb8b99bf552",
    "misleading-green": "1abd4a1d9ba5e8b4c5faa6240bbee14820d34c06f7e82d2bc640e82efb95517a",
    "atomic": "4b79f56e4a8d51d86aa140f596089e6380f99f009e6296812ccc79e3b2aab450",
    "mark-first": "3bf12c01170b9c34fcb84d1c9cb949ee2de169f17422d90509e611b90fdbbbb8",
    "leftover-send": "feecdf969908fe9497b865ace5c94998f7a349073b5b904357d20b8dbed77e6d",
    "never-marks": "213e9f046be295bbf86378031f1c162dadfc2364fae7d2a2e7a4ea1a6aac1e88",
    "raw-sql": "ec9a27ba18591d97f97fa32ea0d19c28cd53dd8869cde5352e00f02bc43a643b",
    "shadow-table": "6e0af2ec354ac8df361a181150d495d37d11cb715472e63b3ea9736e163aab93",
    "tail-bytes": "eaf87826101aa41cc6921a257e77b8d5a6e49de82b537c69e34b6263e8c0115f",
}

STORE_REMEDY = (
    "Kill points are store commits, so a write the store did not make has no kill point and "
    "earns no verdict. Express the same fix through the store: store.send_and_mark(channel, "
    "event_id, payload_bytes) commits the outbox row and its marker together in one durable "
    "transaction; store.sent(event_id), store.send(...), and store.mark_sent(event_id) are the "
    "three-step form; see docs/PRODUCT.md#the-store-api"
)
STORE_API_FALLBACK = (
    "store.sent(event_id) -> bool; store.send(channel, event_id, payload_bytes); "
    "store.mark_sent(event_id); store.send_and_mark(channel, event_id, payload_bytes). Every "
    "call is one durable SQLite commit."
)


class OutboxStore(StoreBase):
    """Fixed trusted store exposed to the candidate handler."""

    def sent(self, event_id: str) -> bool:
        self._require(event_id=event_id)
        with self._connection as connection:
            row = connection.execute(
                "SELECT 1 FROM sent_events WHERE event_id = ?", (event_id,)
            ).fetchone()
        self._settle()
        return row is not None

    def send(self, channel: str, event_id: str, payload_bytes: int) -> None:
        self._require(channel=channel, event_id=event_id, payload_bytes=payload_bytes)
        with self._connection as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE channels SET sent_bytes = sent_bytes + ? WHERE channel = ?",
                (payload_bytes, channel),
            )
            connection.execute(
                "INSERT INTO outbox(event_id, channel, payload_bytes) VALUES (?, ?, ?)",
                (event_id, channel, payload_bytes),
            )
            connection.commit()
        self._pause("send")

    def mark_sent(self, event_id: str) -> None:
        self._require(event_id=event_id)
        with self._connection as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO sent_events(event_id) VALUES (?)", (event_id,))
            connection.commit()
        self._pause("mark_sent")

    def send_and_mark(self, channel: str, event_id: str, payload_bytes: int) -> None:
        self._require(channel=channel, event_id=event_id, payload_bytes=payload_bytes)
        with self._connection as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM sent_events WHERE event_id = ?", (event_id,)
            ).fetchone():
                connection.rollback()
                return
            connection.execute(
                "UPDATE channels SET sent_bytes = sent_bytes + ? WHERE channel = ?",
                (payload_bytes, channel),
            )
            connection.execute(
                "INSERT INTO outbox(event_id, channel, payload_bytes) VALUES (?, ?, ?)",
                (event_id, channel, payload_bytes),
            )
            connection.execute("INSERT INTO sent_events(event_id) VALUES (?)", (event_id,))
            connection.commit()
        self._pause("send_and_mark")


STORE_OPERATIONS = ("send", "mark_sent", "send_and_mark")


def _next_rowid(rows: list[list[object]]) -> int:
    """SQLite's next rowid for a table nothing ever deletes from: one past the largest."""
    return max((row[0] for row in rows if isinstance(row[0], int)), default=0) + 1


def normalize_event(value: object) -> Event:
    if not isinstance(value, Mapping) or set(value) != {"channel", "event_id", "payload_bytes"}:
        raise ValueError("event must contain exactly channel, event_id, and payload_bytes")
    channel, event_id, payload = value["channel"], value["event_id"], value["payload_bytes"]
    if (
        not isinstance(event_id, str)
        or not event_id
        or type(payload) is not int
        or payload <= 0
        or payload > MAX_PAYLOAD_BYTES
        or not isinstance(channel, str)
        or not channel
    ):
        raise ValueError("event fields are invalid")
    return {"channel": channel, "event_id": event_id, "payload_bytes": payload}


def seed_identity(event: Event) -> dict[str, object]:
    return {
        "channel": {"channel": event["channel"], "sent_bytes": INITIAL_SENT_BYTES},
        "journal_mode": "WAL",
        "schema": SCHEMA,
        "schema_version": "1",
        "synchronous": "FULL",
    }


def seed(connection: sqlite3.Connection, event: Event) -> None:
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT INTO channels(channel, sent_bytes) VALUES (?, ?)",
        (event["channel"], INITIAL_SENT_BYTES),
    )


def tables(connection: sqlite3.Connection) -> Tables:
    """Every row of every seeded table, in canonical order; the outbox keeps insertion order."""
    return {
        "channels": [
            list(row)
            for row in connection.execute(
                "SELECT rowid, channel, sent_bytes FROM channels ORDER BY channel"
            )
        ],
        "outbox": [
            list(row)
            for row in connection.execute(
                "SELECT id, event_id, channel, payload_bytes FROM outbox ORDER BY id"
            )
        ],
        "sent_events": [
            list(row)
            for row in connection.execute(
                "SELECT rowid, event_id FROM sent_events ORDER BY event_id"
            )
        ],
    }


def snapshot(rows: Tables, event: Event) -> StateSnapshot:
    """The four numbers a receipt carries: channel bytes, outbox rows, their total, the marker."""
    sent_bytes = next((row[2] for row in rows["channels"] if row[1] == event["channel"]), None)
    if not isinstance(sent_bytes, int):
        raise ValueError("the event's channel row is missing")
    outbox = [row for row in rows["outbox"] if row[1] == event["event_id"]]
    total = sum(row[3] for row in outbox if isinstance(row[3], int))
    marker = sum(1 for row in rows["sent_events"] if row[1] == event["event_id"])
    return StateSnapshot.with_digest(
        subject_total=sent_bytes,
        event_effect_count=len(outbox),
        event_effect_total=total,
        event_marker_count=marker,
    )


def apply(rows: Tables, operation: str, event: Event) -> Tables:
    """What the database must hold after the named store commit, and nothing else."""
    channel, event_id, payload = event["channel"], event["event_id"], event["payload_bytes"]
    after: Tables = {name: [list(row) for row in table] for name, table in rows.items()}
    if operation in {"send", "send_and_mark"}:
        for row in after["channels"]:
            if row[1] == channel and isinstance(row[2], int) and isinstance(payload, int):
                row[2] = row[2] + payload
        after["outbox"].append([_next_rowid(after["outbox"]), event_id, channel, payload])
    if operation in {"mark_sent", "send_and_mark"}:
        after["sent_events"] = sorted(
            [*after["sent_events"], [_next_rowid(after["sent_events"]), event_id]],
            key=lambda row: str(row[1]),
        )
    if operation not in STORE_OPERATIONS:
        raise ValueError(f"unknown store operation {operation!r}")
    return after


def effect_delta(event: Event) -> int:
    payload = event["payload_bytes"]
    assert isinstance(payload, int)
    return payload


def initial_total(event: Event) -> int:
    return INITIAL_SENT_BYTES


def checkpoint_reached(snapshot: StateSnapshot, event: Event, boundary: FaultBoundary) -> bool:
    """The capsule's kill point: one durable outbox row, plus its marker at the marker boundary."""
    payload = effect_delta(event)
    return (
        snapshot.subject_total == INITIAL_SENT_BYTES + payload
        and snapshot.event_effect_count == 1
        and snapshot.event_effect_total == payload
        and (boundary is FaultBoundary.EFFECT_COMMIT or snapshot.event_marker_count == 1)
    )


def format_subject(sent_bytes: int) -> str:
    return f"{sent_bytes} byte{'' if sent_bytes == 1 else 's'}"


def describe_final(final: StateSnapshot, event: Event) -> str:
    event_id = event["event_id"]
    expected = INITIAL_SENT_BYTES + effect_delta(event)
    rows = f"{final.event_effect_count} outbox row{'s' if final.event_effect_count != 1 else ''}"
    marker = f"{final.event_marker_count} marker"
    if final.event_effect_count == 0 and final.event_marker_count == 1:
        cause = f"{event_id} was marked sent but nothing was ever sent, so the message is lost"
    elif final.event_effect_count == 1 and final.event_marker_count == 0:
        cause = f"{event_id} was sent but never marked sent, so the next retry sends it again"
    elif final.event_effect_count == 2:
        cause = f"{event_id} was sent twice"
    elif final.event_effect_count > 2:
        cause = f"{event_id} was sent {final.event_effect_count} times"
    else:
        cause = "the final state matches neither exactly-once nor the capsule's duplicate shape"
    return (
        f"{format_subject(final.subject_total)} on the channel instead of "
        f"{format_subject(expected)} ({rows}, {marker}): {cause}"
    )


def verdict_summary(verdict: CrashVerdict, event: Event) -> str:
    event_id, payload = event["event_id"], event["payload_bytes"]
    assert isinstance(payload, int)
    once = format_subject(INITIAL_SENT_BYTES + payload)
    twice = format_subject(INITIAL_SENT_BYTES + 2 * payload)
    return {
        CrashVerdict.BUG_REPRODUCED: (
            f"The base replayed {event_id} to a durable double send ({twice} on the channel, "
            f"expected {once})."
        ),
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES: (
            f"The candidate replayed {event_id} to a durable double send ({twice} on the "
            f"channel, expected {once})."
        ),
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN: (
            "The candidate completed every world in a state that is neither exactly-once nor "
            "the capsule's duplicate."
        ),
        CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE: (
            f"Five fresh worlds ended at exactly {once} on the channel, one outbox row, and one "
            "marker."
        ),
        CrashVerdict.EVIDENCE_INCOMPLETE: "Required crash evidence was incomplete.",
        CrashVerdict.UNSUPPORTED_TARGET: "The supplied target is unsupported.",
    }[verdict]


SCENARIO = Scenario(
    scenario_id=SCENARIO_ID,
    adapter_id="outbox-store-v1",
    fault_intent_id="first-send-effect-commit-v1",
    probe_id="outbox-state-v1",
    predicate_id="single-send-and-marker-v1",
    event_fixture_id="msg-1-v1",
    target="app.outbox:dispatch_outbox",
    fixture_package="sqlite_outbox_v1",
    handler_relative="app/outbox.py",
    common_files=(
        ("common/app/__init__.py", "app/__init__.py"),
        ("common/tests/test_outbox.py", "tests/test_outbox.py"),
    ),
    hero_variants=HERO_VARIANTS,
    zoo_variants=ZOO_VARIANTS,
    tree_digests=TREE_DIGESTS,
    issue_digest=ISSUE_DIGEST,
    event_digest=EVENT_DIGEST,
    event_resource_digest=EVENT_RESOURCE_DIGEST,
    audited_contract_digest=AUDITED_CONTRACT_DIGEST,
    contract_resource_digest=CONTRACT_RESOURCE_DIGEST,
    repro_dir="double-send",
    schema=SCHEMA,
    seed_identity=seed_identity,
    seed=seed,
    tables=tables,
    snapshot=snapshot,
    apply=apply,
    store_operations=STORE_OPERATIONS,
    store_class=OutboxStore,
    store_remedy=STORE_REMEDY,
    store_api_fallback=STORE_API_FALLBACK,
    normalize_event=normalize_event,
    effect_delta=effect_delta,
    initial_total=initial_total,
    checkpoint_reached=checkpoint_reached,
    scalar_name="payload_bytes",
    scalar_bounds=(1, MAX_PAYLOAD_BYTES),
    subject_noun="sent payload",
    effect_noun="send",
    effect_verb="sends",
    others_noun="other channels or messages",
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
    "INITIAL_SENT_BYTES",
    "ISSUE_DIGEST",
    "MAX_PAYLOAD_BYTES",
    "SCENARIO",
    "SCENARIO_ID",
    "SCHEMA",
    "STORE_OPERATIONS",
    "STORE_REMEDY",
    "TREE_DIGESTS",
    "ZOO_VARIANTS",
    "OutboxStore",
]
