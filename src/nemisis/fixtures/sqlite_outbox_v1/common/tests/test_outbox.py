from app.outbox import OutboxEvent, dispatch_outbox


class MemoryStore:
    def __init__(self) -> None:
        self.sent_bytes = 0
        self.sent_events: set[str] = set()

    def sent(self, event_id: str) -> bool:
        return event_id in self.sent_events

    def send(self, channel: str, event_id: str, payload_bytes: int) -> None:
        self.sent_bytes += payload_bytes

    def mark_sent(self, event_id: str) -> None:
        self.sent_events.add(event_id)

    def send_and_mark(self, channel: str, event_id: str, payload_bytes: int) -> None:
        if not self.sent(event_id):
            self.send(channel, event_id, payload_bytes)
            self.mark_sent(event_id)


def test_sends_the_message_once() -> None:
    store = MemoryStore()
    event: OutboxEvent = {"event_id": "msg-1", "channel": "billing-webhook", "payload_bytes": 512}

    dispatch_outbox(store, event)

    assert store.sent_bytes == 512
