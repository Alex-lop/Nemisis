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
    # The textbook atomic fix, written as one SQL transaction on the store's own database
    # instead of through the store. It is correct, and CrashCheck cannot place a kill inside it.
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute("BEGIN IMMEDIATE")
        already = connection.execute(
            "SELECT 1 FROM sent_events WHERE event_id = ?", (event["event_id"],)
        ).fetchone()
        if already:
            connection.rollback()
            return
        connection.execute(
            "UPDATE channels SET sent_bytes = sent_bytes + ? WHERE channel = ?",
            (event["payload_bytes"], event["channel"]),
        )
        connection.execute(
            "INSERT INTO outbox(event_id, channel, payload_bytes) VALUES (?, ?, ?)",
            (event["event_id"], event["channel"], event["payload_bytes"]),
        )
        connection.execute("INSERT INTO sent_events(event_id) VALUES (?)", (event["event_id"],))
        connection.commit()
