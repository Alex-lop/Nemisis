"""Inventory reservation handler used by the CrashCheck inventory scenario."""

from typing import Protocol, TypedDict


class ReservationEvent(TypedDict):
    event_id: str
    sku: str
    quantity: int


class InventoryStore(Protocol):
    def reserved(self, event_id: str) -> bool: ...

    def reserve(self, sku: str, event_id: str, quantity: int) -> None: ...

    def mark_reserved(self, event_id: str) -> None: ...

    def reserve_and_mark(self, sku: str, event_id: str, quantity: int) -> None: ...


def reserve_inventory(store: InventoryStore, event: ReservationEvent) -> None:
    order_id = event["event_id"]
    if store.reserved(order_id):
        return
    store.reserve(event["sku"], order_id, event["quantity"])
    store.mark_reserved(order_id)
