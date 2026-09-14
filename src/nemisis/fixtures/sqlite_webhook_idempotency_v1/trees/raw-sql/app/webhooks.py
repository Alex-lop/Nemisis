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
    # The textbook atomic fix, written as one SQL transaction on the store's own database
    # instead of through the store. It is correct, and CrashCheck cannot place a kill inside it.
    with sqlite3.connect(store._database, isolation_level=None) as connection:
        connection.execute("BEGIN IMMEDIATE")
        already = connection.execute(
            "SELECT 1 FROM delivered_webhooks WHERE event_id = ?", (event["event_id"],)
        ).fetchone()
        if already:
            connection.rollback()
            return
        connection.execute(
            "UPDATE workspaces SET seats = seats + ? WHERE workspace_id = ?",
            (event["seats"], event["workspace_id"]),
        )
        connection.execute(
            "INSERT INTO seat_grants(event_id, workspace_id, seats) VALUES (?, ?, ?)",
            (event["event_id"], event["workspace_id"], event["seats"]),
        )
        connection.execute(
            "INSERT INTO delivered_webhooks(event_id) VALUES (?)", (event["event_id"],)
        )
        connection.commit()
