from app.inventory import ReservationEvent, reserve_inventory


class MemoryStore:
    def __init__(self) -> None:
        self.on_hand = 10
        self.reserved_orders: set[str] = set()

    def reserved(self, event_id: str) -> bool:
        return event_id in self.reserved_orders

    def reserve(self, sku: str, event_id: str, quantity: int) -> None:
        self.on_hand -= quantity

    def mark_reserved(self, event_id: str) -> None:
        self.reserved_orders.add(event_id)

    def reserve_and_mark(self, sku: str, event_id: str, quantity: int) -> None:
        if not self.reserved(event_id):
            self.reserve(sku, event_id, quantity)
            self.mark_reserved(event_id)


def test_reserves_stock() -> None:
    store = MemoryStore()
    event: ReservationEvent = {"event_id": "order-1", "sku": "widget", "quantity": 2}

    reserve_inventory(store, event)

    assert store.on_hand == 8
