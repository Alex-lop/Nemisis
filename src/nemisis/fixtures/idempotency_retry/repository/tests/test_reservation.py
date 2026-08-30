from inventory import reserve_inventory


def test_reserves_available_inventory() -> None:
    stock = {"widget": 10}

    reserve_inventory(stock, set(), "order-1", "widget", 2)

    assert stock == {"widget": 8}
