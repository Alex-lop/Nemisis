"""Outbox dispatch handler used by the CrashCheck outbox scenario."""

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
    message_id = event["event_id"]
    if store.sent(message_id):
        return
    store.mark_sent(message_id)
    store.send(event["channel"], message_id, event["payload_bytes"])
