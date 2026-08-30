# Make inventory reservation retry-safe

Make `reserve_inventory` idempotent by order ID. Retrying an order must not decrement
inventory twice, including when the first attempt crashes after decrementing inventory but
before returning to the caller.
