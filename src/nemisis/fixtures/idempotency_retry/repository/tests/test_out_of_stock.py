import pytest
from inventory import reserve_inventory


def test_rejects_insufficient_inventory_without_decrementing() -> None:
    stock = {"widget": 1}

    with pytest.raises(ValueError, match="insufficient inventory"):
        reserve_inventory(stock, set(), "order-1", "widget", 2)

    assert stock == {"widget": 1}
