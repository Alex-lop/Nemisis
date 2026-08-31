"""Account-credit handler used by the CrashCheck hero."""

from typing import Protocol, TypedDict


class CreditEvent(TypedDict):
    event_id: str
    account_id: str
    amount_cents: int


class CreditStore(Protocol):
    def processed(self, event_id: str) -> bool: ...

    def credit(self, account_id: str, event_id: str, amount_cents: int) -> None: ...

    def mark_processed(self, event_id: str) -> None: ...

    def credit_and_mark(self, account_id: str, event_id: str, amount_cents: int) -> None: ...


def apply_credit(store: CreditStore, event: CreditEvent) -> None:
    event_id = event["event_id"]
    if store.processed(event_id):
        return
    store.credit(event["account_id"], event_id, event["amount_cents"])
    store.mark_processed(event_id)
