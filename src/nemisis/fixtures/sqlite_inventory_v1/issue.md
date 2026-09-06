# Inventory reserved twice after a retry

A timeout followed by a retry occasionally reserves the same order's stock twice, so
`widget` reads two units short of what was actually sold. We cannot reproduce it locally.

Make `app.inventory:reserve_inventory` idempotent by order ID. Retrying `order-1` must leave
`widget` at exactly 8 units, reserved once, from a stock of 10.
