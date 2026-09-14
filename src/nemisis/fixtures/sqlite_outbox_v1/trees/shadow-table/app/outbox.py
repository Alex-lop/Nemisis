"""Outbox dispatch handler used by the CrashCheck outbox scenario."""

import sqlite3
from typing import Protocol, TypedDict


class OutboxEvent(TypedDict):
    event_id: str
    channel: str
    payload_bytes: int


class OutboxStore(Protocol):
    def sent(self, event_id: str) -> bool: ...

    def send(self, channel: str, event_id: str, payload_bytes: int) -> None: ...

    def mark_sent(self, event_id: str) -> None: ...

    def send_and_mark(self, channel: str, event_id: str, payload_bytes: int) -> None: ...


def dispatch_outbox(store: OutboxStore, event: OutboxEvent) -> None:
    # Dedup state kept in a table the handler creates inside the store's own database, written
    # before the send. A crash between this commit and the store's leaves the message marked
    # in-flight and never sent; no store commit sits inside that window.
    event_id = event["event_id"]
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS inflight(event_id TEXT PRIMARY KEY)")
        if connection.execute("SELECT 1 FROM inflight WHERE event_id = ?", (event_id,)).fetchone():
            return
        connection.execute("INSERT INTO inflight(event_id) VALUES (?)", (event_id,))
        connection.commit()
    store.send_and_mark(event["channel"], event_id, event["payload_bytes"])
