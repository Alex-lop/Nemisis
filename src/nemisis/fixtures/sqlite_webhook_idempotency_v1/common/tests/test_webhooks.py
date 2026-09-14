from app.webhooks import WebhookEvent, handle_webhook


class MemoryStore:
    def __init__(self) -> None:
        self.seats = 1
        self.delivered_webhooks: set[str] = set()

    def processed(self, event_id: str) -> bool:
        return event_id in self.delivered_webhooks

    def grant(self, workspace_id: str, event_id: str, seats: int) -> None:
        self.seats += seats

    def mark_processed(self, event_id: str) -> None:
        self.delivered_webhooks.add(event_id)

    def grant_and_mark(self, workspace_id: str, event_id: str, seats: int) -> None:
        if not self.processed(event_id):
            self.grant(workspace_id, event_id, seats)
            self.mark_processed(event_id)


def test_grants_the_purchased_seats() -> None:
    store = MemoryStore()
    event: WebhookEvent = {"event_id": "evt_whk_88", "workspace_id": "ws_acme", "seats": 3}

    handle_webhook(store, event)

    assert store.seats == 4
