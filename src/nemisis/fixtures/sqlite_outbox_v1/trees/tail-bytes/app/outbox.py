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
    # The atomic fix, then sixteen bytes appended past the database file's last page after the
    # handler's last store commit. The credit scenario's twin of this tree is the shape the
    # nightly red team turned into a real engine fix on 2026-09-11: a checkpoint on the store's
    # close truncated the file back to its page count, so an engine that read it only after the
    # worker had exited never saw the write. The kernel now reads before the exit, and the write
    # forfeits the verdict here too.
    if store.sent(event["event_id"]):
        return
    store.send_and_mark(event["channel"], event["event_id"], event["payload_bytes"])
    with open(store._database, "ab") as tail:
        tail.write(b"\x5a" * 16)
