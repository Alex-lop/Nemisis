"""A deliberately broken inventory reservation service."""


def reserve_inventory(
    stock: dict[str, int],
    processed_orders: set[str],
    order_id: str,
    sku: str,
    quantity: int,
    *,
    crash_after_decrement: bool = False,
) -> None:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if stock.get(sku, 0) < quantity:
        raise ValueError("insufficient inventory")

    stock[sku] -= quantity
    if crash_after_decrement:
        raise RuntimeError("simulated crash after inventory decrement")
