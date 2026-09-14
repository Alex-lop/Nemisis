"""Webhook delivery handler used by the CrashCheck webhook-idempotency scenario."""

import sqlite3
from typing import Protocol, TypedDict


class WebhookEvent(TypedDict):
    event_id: str
    workspace_id: str
    seats: int


class WebhookStore(Protocol):
    def processed(self, event_id: str) -> bool: ...

    def grant(self, workspace_id: str, event_id: str, seats: int) -> None: ...

    def mark_processed(self, event_id: str) -> None: ...

    def grant_and_mark(self, workspace_id: str, event_id: str, seats: int) -> None: ...


def handle_webhook(store: WebhookStore, event: WebhookEvent) -> None:
    # A second idempotency table the handler keeps for itself inside the store's own database,
    # written before the grant. A crash between this commit and the store's leaves the delivery
    # marked in-flight and no seats granted; no store commit sits inside that window.
    event_id = event["event_id"]
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS inflight(event_id TEXT PRIMARY KEY)")
        if connection.execute("SELECT 1 FROM inflight WHERE event_id = ?", (event_id,)).fetchone():
            return
        connection.execute("INSERT INTO inflight(event_id) VALUES (?)", (event_id,))
        connection.commit()
    store.grant_and_mark(event["workspace_id"], event_id, event["seats"])
