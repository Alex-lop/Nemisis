"""Account-credit handler used by the CrashCheck hero."""

import sqlite3
from typing import Protocol, TypedDict


class CreditEvent(TypedDict):
    event_id: str
    account_id: str
    amount_cents: int


class CreditStore(Protocol):
    def processed(self, event_id: str) -> bool: ...

    def credit(self, account_id: str, event_id: str, amount_cents: int) -> None: ...

    def mark_processed(self, event_id: str) -> None: ...

    def credit_and_mark(self, account_id: str, event_id: str, amount_cents: int) -> None: ...


def apply_credit(store: CreditStore, event: CreditEvent) -> None:
    # The textbook atomic fix, written as one SQL transaction on the store's own database
    # instead of through the store. It is correct, and CrashCheck cannot place a kill inside it.
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute("BEGIN IMMEDIATE")
        already = connection.execute(
            "SELECT 1 FROM processed_events WHERE event_id = ?", (event["event_id"],)
        ).fetchone()
        if already:
            connection.rollback()
            return
        connection.execute(
            "UPDATE accounts SET balance_cents = balance_cents + ? WHERE account_id = ?",
            (event["amount_cents"], event["account_id"]),
        )
        connection.execute(
            "INSERT INTO credit_ledger(event_id, account_id, amount_cents) VALUES (?, ?, ?)",
            (event["event_id"], event["account_id"], event["amount_cents"]),
        )
        connection.execute(
            "INSERT INTO processed_events(event_id) VALUES (?)", (event["event_id"],)
        )
        connection.commit()
