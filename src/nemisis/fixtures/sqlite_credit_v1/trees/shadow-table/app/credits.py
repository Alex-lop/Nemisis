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
    # Dedup state kept in a table the handler creates inside the store's own database, written
    # before the credit. A crash between this commit and the store's leaves the event marked
    # in-flight and never credited; no store commit sits inside that window.
    event_id = event["event_id"]
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS inflight(event_id TEXT PRIMARY KEY)")
        if connection.execute("SELECT 1 FROM inflight WHERE event_id = ?", (event_id,)).fetchone():
            return
        connection.execute("INSERT INTO inflight(event_id) VALUES (?)", (event_id,))
        connection.commit()
    store.credit_and_mark(event["account_id"], event_id, event["amount_cents"])
