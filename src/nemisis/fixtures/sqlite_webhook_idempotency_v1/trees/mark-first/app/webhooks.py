"""Webhook delivery handler used by the CrashCheck webhook-idempotency scenario."""

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
    delivery_id = event["event_id"]
    if store.processed(delivery_id):
        return
    store.mark_processed(delivery_id)
    store.grant(event["workspace_id"], delivery_id, event["seats"])
