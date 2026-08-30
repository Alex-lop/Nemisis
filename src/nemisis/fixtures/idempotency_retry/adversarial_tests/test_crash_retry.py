import pytest
from inventory import reserve_inventory


def test_crash_then_retry_does_not_decrement_twice() -> None:
    stock = {"widget": 10}
    processed_orders: set[str] = set()

    with pytest.raises(RuntimeError, match="simulated crash"):
        reserve_inventory(
            stock,
            processed_orders,
            "order-1",
            "widget",
            2,
            crash_after_decrement=True,
        )
    reserve_inventory(stock, processed_orders, "order-1", "widget", 2)

    assert stock == {"widget": 8}
