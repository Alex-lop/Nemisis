# The same webhook is delivered twice after a retry

A timeout followed by a retry occasionally writes `msg-1` to the outbox twice, so the billing
webhook fires a second time and the customer is charged a second notification. We cannot
reproduce it locally.

Make `app.outbox:dispatch_outbox` idempotent by message ID. Retrying `msg-1` must leave exactly
one outbox row for `billing-webhook`, 512 bytes sent, marked sent once.
