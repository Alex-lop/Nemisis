from inventory import reserve_inventory


def test_ordinary_duplicate_retry_does_not_decrement_twice() -> None:
    stock = {"widget": 10}
    processed_orders: set[str] = set()

    reserve_inventory(stock, processed_orders, "order-1", "widget", 2)
    reserve_inventory(stock, processed_orders, "order-1", "widget", 2)

    assert stock == {"widget": 8}
