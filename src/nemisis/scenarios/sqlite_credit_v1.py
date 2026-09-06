"""``sqlite-credit-v1``: one account credit, doubled by a crash between credit and marker."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from nemisis.crash_models import CrashVerdict, CreditSnapshot, FaultBoundary
from nemisis.hashing import sha256_json
from nemisis.report import money
from nemisis.scenario import Event, Scenario, StoreBase, connect

SCENARIO_ID = "sqlite-credit-v1"
SCHEMA = """
CREATE TABLE accounts(
    account_id TEXT PRIMARY KEY,
    balance_cents INTEGER NOT NULL
);
CREATE TABLE credit_ledger(
    id INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL
);
CREATE TABLE processed_events(event_id TEXT PRIMARY KEY);
"""

ISSUE_DIGEST = "dca9933dc39177cd391972f8ec6945b01a27d3559990566788cabb12c51c0f77"
EVENT_DIGEST = "4ad9ce16a3a060a5dbde7dffafdd7fd2f047e612c4e34c6ca30635355778b293"
EVENT_RESOURCE_DIGEST = "95db3d29c50d2c2bbb0058e4e82d8705c77e51a98e25887defc8366e96bd0e33"
AUDITED_CONTRACT_DIGEST = "3b121eed2abbb011d5e769600690c5502bca561233007b0df5787cd49fb67e10"
CONTRACT_RESOURCE_DIGEST = "e364533418ea5060fb6abb17b0aa84ab633315d51b7f02646acb7a0dc5fa7249"
# The three-tree hero, in canonical order, then the candidate zoo found by red-teaming the
# checker. Each zoo member fooled or nearly fooled an earlier engine, except raw-sql, which is
# the textbook fix a judge writes as one SQL transaction and which earns a remedy, not a verdict.
HERO_VARIANTS = ("buggy", "misleading-green", "atomic")
ZOO_VARIANTS = ("mark-first", "leftover-credit", "never-marks", "raw-sql")
TREE_DIGESTS: Mapping[str, str] = {
    "buggy": "e0e3df5d3bdd0659fd4fcd7719c9047186eb2099dbab2bbb8092c1903a97c0b2",
    "misleading-green": "3d79be420d3a92ee84ac66c15576d1fbfdb7ec3dba4f34dd9e6bfeb8489bf69f",
    "atomic": "ccdce21b146ff0146fd93f3aa86f3d047f937153215cae4e2ab80c92d93954de",
    "mark-first": "6dc1d31beec8c34ecc7369654cd6d47146af7ee7e1f15d762e33cb8b036b5f97",
    "leftover-credit": "af991a61516c1d1b4cfbc2119dd8d937a8a92936cf82d90086bba4fdb40da807",
    "never-marks": "7a9fda4e62e304c3aaa604b97ee1ea4f68c92edbe3fc1e90228b01af6dcd862d",
    "raw-sql": "09e6dc5d9abafa8736c934516a30a9811b53f710b07fe19bff6882cfdc88bc67",
}

# What a handler that wrote around the store is told, on the first run, in the summary and report.
STORE_REMEDY = (
    "Kill points are store commits, so a write the store did not make has no kill point and "
    "earns no verdict. Express the same fix through the store: store.credit_and_mark(account_id, "
    "event_id, amount_cents) commits the credit and its marker together in one durable "
    "transaction; store.processed(event_id), store.credit(...), and store.mark_processed(event_id) "
    "are the three-step form; see docs/PRODUCT.md#the-store-api"
)
STORE_API_FALLBACK = (
    "store.processed(event_id) -> bool; store.credit(account_id, event_id, amount_cents); "
    "store.mark_processed(event_id); store.credit_and_mark(account_id, event_id, "
    "amount_cents). Every call is one durable SQLite commit."
)


class CreditStore(StoreBase):
    """Fixed trusted store exposed to the candidate handler."""

    def processed(self, event_id: str) -> bool:
        self._require(event_id=event_id)
        with connect(self._database) as connection:
            row = connection.execute(
                "SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return row is not None

    def credit(self, account_id: str, event_id: str, amount_cents: int) -> None:
        self._require(account_id=account_id, event_id=event_id, amount_cents=amount_cents)
        with connect(self._database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE accounts SET balance_cents = balance_cents + ? WHERE account_id = ?",
                (amount_cents, account_id),
            )
            connection.execute(
                "INSERT INTO credit_ledger(event_id, account_id, amount_cents) VALUES (?, ?, ?)",
                (event_id, account_id, amount_cents),
            )
            connection.commit()
        self._pause("credit")

    def mark_processed(self, event_id: str) -> None:
        self._require(event_id=event_id)
        with connect(self._database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO processed_events(event_id) VALUES (?)", (event_id,))
            connection.commit()
        self._pause("mark_processed")

    def credit_and_mark(self, account_id: str, event_id: str, amount_cents: int) -> None:
        self._require(account_id=account_id, event_id=event_id, amount_cents=amount_cents)
        with connect(self._database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,)
            ).fetchone():
                connection.rollback()
                return
            connection.execute(
                "UPDATE accounts SET balance_cents = balance_cents + ? WHERE account_id = ?",
                (amount_cents, account_id),
            )
            connection.execute(
                "INSERT INTO credit_ledger(event_id, account_id, amount_cents) VALUES (?, ?, ?)",
                (event_id, account_id, amount_cents),
            )
            connection.execute("INSERT INTO processed_events(event_id) VALUES (?)", (event_id,))
            connection.commit()
        self._pause("credit_and_mark")


# What each trusted store operation may change: (balance, ledger rows, ledger total, marker).
STORE_OPERATIONS: Mapping[str, Any] = {
    "credit": lambda event: (event["amount_cents"], 1, event["amount_cents"], 0),
    "mark_processed": lambda event: (0, 0, 0, 1),
    "credit_and_mark": lambda event: (event["amount_cents"], 1, event["amount_cents"], 1),
}


def normalize_event(value: object) -> Event:
    if not isinstance(value, Mapping) or set(value) != {"account_id", "amount_cents", "event_id"}:
        raise ValueError("event must contain exactly account_id, amount_cents, and event_id")
    account_id, amount, event_id = value["account_id"], value["amount_cents"], value["event_id"]
    if (
        not isinstance(account_id, str)
        or not account_id
        or type(amount) is not int
        or amount <= 0
        or not isinstance(event_id, str)
        or not event_id
    ):
        raise ValueError("event fields are invalid")
    return {"account_id": account_id, "amount_cents": amount, "event_id": event_id}


def seed_identity(event: Event) -> dict[str, object]:
    """The logical seed, digested independently from SQLite file layout."""
    return {
        "account": {"account_id": event["account_id"], "balance_cents": 0},
        "journal_mode": "WAL",
        "schema": SCHEMA,
        "schema_version": "1",
        "synchronous": "FULL",
    }


def seed(connection: sqlite3.Connection, event: Event) -> None:
    connection.executescript(SCHEMA)
    connection.execute(
        "INSERT INTO accounts(account_id, balance_cents) VALUES (?, 0)", (event["account_id"],)
    )


def probe(connection: sqlite3.Connection, event: Event) -> CreditSnapshot:
    account = connection.execute(
        "SELECT balance_cents FROM accounts WHERE account_id = ?", (event["account_id"],)
    ).fetchone()
    ledger = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM credit_ledger WHERE event_id = ?",
        (event["event_id"],),
    ).fetchone()
    marker = connection.execute(
        "SELECT COUNT(*) FROM processed_events WHERE event_id = ?", (event["event_id"],)
    ).fetchone()
    if account is None or ledger is None or marker is None:
        raise sqlite3.OperationalError("read-only state probe was incomplete")
    return CreditSnapshot.with_digest(
        account_balance_cents=int(account[0]),
        event_ledger_count=int(ledger[0]),
        event_ledger_total_cents=int(ledger[1]),
        event_marker_count=int(marker[0]),
    )


def others(connection: sqlite3.Connection, event: Event) -> dict[str, list[list[object]]]:
    """Every row that is not this event's: they must never change during a run."""
    rows = {
        "accounts": connection.execute(
            "SELECT account_id, balance_cents FROM accounts WHERE account_id IS NOT ? "
            "ORDER BY account_id",
            (event["account_id"],),
        ).fetchall(),
        "credit_ledger": connection.execute(
            "SELECT id, event_id, account_id, amount_cents FROM credit_ledger "
            "WHERE event_id IS NOT ? ORDER BY id",
            (event["event_id"],),
        ).fetchall(),
        "processed_events": connection.execute(
            "SELECT event_id FROM processed_events WHERE event_id IS NOT ? ORDER BY event_id",
            (event["event_id"],),
        ).fetchall(),
    }
    return {name: [list(row) for row in table] for name, table in rows.items()}


# The seed has exactly one account (this event's) and nothing else, so every other row set is
# empty. Any later difference means something wrote around the trusted store.
SEEDED_OTHERS_DIGEST = sha256_json({"accounts": [], "credit_ledger": [], "processed_events": []})


def effect_delta(event: Event) -> int:
    amount = event["amount_cents"]
    assert isinstance(amount, int)
    return amount


def checkpoint_reached(snapshot: CreditSnapshot, event: Event, boundary: FaultBoundary) -> bool:
    """The capsule's kill point: one durable credit, plus its marker at the marker boundary."""
    amount = effect_delta(event)
    return (
        snapshot.account_balance_cents == amount
        and snapshot.event_ledger_count == 1
        and snapshot.event_ledger_total_cents == amount
        and (boundary is FaultBoundary.EFFECT_COMMIT or snapshot.event_marker_count == 1)
    )


def _plus_dollars(cents: int) -> str:
    return f"+${cents // 100}" if cents % 100 == 0 else f"+${cents / 100:.2f}"


def describe_final(final: CreditSnapshot, event_id: str, amount: int) -> str:
    money_now = money(final.account_balance_cents)
    rows = f"{final.event_ledger_count} ledger row{'s' if final.event_ledger_count != 1 else ''}"
    marker = f"{final.event_marker_count} marker"
    if final.event_ledger_count == 0 and final.event_marker_count == 1:
        cause = f"{event_id} was marked processed but never credited, so the credit is lost"
    elif final.event_ledger_count == 2:
        cause = f"{event_id} was credited twice"
    elif final.event_ledger_count > 2:
        cause = f"{event_id} was credited {final.event_ledger_count} times"
    else:
        cause = "the final state matches neither exactly-once nor the capsule's duplicate shape"
    return f"{money_now} instead of {money(amount)} ({rows}, {marker}): {cause}"


def verdict_summary(verdict: CrashVerdict, event_id: str, amount: int) -> str:
    duplicate = _plus_dollars(amount * 2)
    return {
        CrashVerdict.BUG_REPRODUCED: (
            f"The base replayed {event_id} to a durable {duplicate} duplicate effect."
        ),
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES: (
            f"The candidate replayed {event_id} to a durable {duplicate} duplicate effect."
        ),
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN: (
            "The candidate completed every world in a state that is neither exactly-once nor "
            "the capsule's duplicate."
        ),
        CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE: (
            f"Five fresh worlds ended at exactly {_plus_dollars(amount)}, one ledger effect, and "
            "one marker."
        ),
        CrashVerdict.EVIDENCE_INCOMPLETE: "Required crash evidence was incomplete.",
        CrashVerdict.UNSUPPORTED_TARGET: "The supplied target is unsupported.",
    }[verdict]


SCENARIO = Scenario(
    scenario_id=SCENARIO_ID,
    adapter_id="credit-store-v1",
    fault_intent_id="first-credit-effect-commit-v1",
    probe_id="credit-state-v1",
    predicate_id="single-credit-and-marker-v1",
    event_fixture_id="evt-1042-v1",
    target="app.credits:apply_credit",
    fixture_package="sqlite_credit_v1",
    handler_relative="app/credits.py",
    common_files=(
        ("common/app/__init__.py", "app/__init__.py"),
        ("common/tests/test_credits.py", "tests/test_credits.py"),
    ),
    hero_variants=HERO_VARIANTS,
    zoo_variants=ZOO_VARIANTS,
    tree_digests=TREE_DIGESTS,
    issue_digest=ISSUE_DIGEST,
    event_digest=EVENT_DIGEST,
    event_resource_digest=EVENT_RESOURCE_DIGEST,
    audited_contract_digest=AUDITED_CONTRACT_DIGEST,
    contract_resource_digest=CONTRACT_RESOURCE_DIGEST,
    repro_dir="double-credit",
    schema=SCHEMA,
    seed_identity=seed_identity,
    seed=seed,
    probe=probe,
    others=others,
    seeded_others_digest=SEEDED_OTHERS_DIGEST,
    store_class=CreditStore,
    store_operations=STORE_OPERATIONS,
    store_remedy=STORE_REMEDY,
    store_api_fallback=STORE_API_FALLBACK,
    normalize_event=normalize_event,
    effect_delta=effect_delta,
    checkpoint_reached=checkpoint_reached,
    effect_noun="credit",
    describe_final=describe_final,
    verdict_summary=verdict_summary,
)

__all__ = [
    "AUDITED_CONTRACT_DIGEST",
    "CONTRACT_RESOURCE_DIGEST",
    "EVENT_DIGEST",
    "EVENT_RESOURCE_DIGEST",
    "HERO_VARIANTS",
    "ISSUE_DIGEST",
    "SCENARIO",
    "SCENARIO_ID",
    "SCHEMA",
    "STORE_OPERATIONS",
    "STORE_REMEDY",
    "TREE_DIGESTS",
    "ZOO_VARIANTS",
    "CreditStore",
]
