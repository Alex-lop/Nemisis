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
    # The atomic fix, then sixteen bytes appended past the database file's last page after the
    # handler's last store commit. Closing the store's connection checkpoints the WAL, and a
    # checkpoint truncates the file back to its page count, so an engine that read the file only
    # after the worker had exited never saw the write: this shape earned FIX_PROVEN_FOR_THIS_CAPSULE
    # in the nightly red team on 2026-09-11 (GitHub run 34593382316, cases 16 and 87). The kernel
    # now reads the file before the worker may exit, and the write forfeits the verdict.
    if store.processed(event["event_id"]):
        return
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
    with open(store._database, "ab") as tail:
        tail.write(b"\x5a" * 16)
