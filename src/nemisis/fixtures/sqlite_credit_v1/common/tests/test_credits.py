from app.credits import CreditEvent, apply_credit


class MemoryStore:
    def __init__(self) -> None:
        self.balance_cents = 0
        self.processed_events: set[str] = set()

    def processed(self, event_id: str) -> bool:
        return event_id in self.processed_events

    def credit(self, account_id: str, event_id: str, amount_cents: int) -> None:
        self.balance_cents += amount_cents

    def mark_processed(self, event_id: str) -> None:
        self.processed_events.add(event_id)

    def credit_and_mark(self, account_id: str, event_id: str, amount_cents: int) -> None:
        if not self.processed(event_id):
            self.credit(account_id, event_id, amount_cents)
            self.mark_processed(event_id)


def test_applies_credit() -> None:
    store = MemoryStore()
    event: CreditEvent = {
        "event_id": "evt_1042",
        "account_id": "acct_7",
        "amount_cents": 2500,
    }

    apply_credit(store, event)

    assert store.balance_cents == 2500
