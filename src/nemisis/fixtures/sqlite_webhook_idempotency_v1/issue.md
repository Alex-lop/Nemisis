# Seats granted twice when the provider redelivers a webhook

Our `checkout.session.completed` endpoint sometimes answers too slowly, the provider redelivers
the same event, and the workspace ends up holding the seats twice. Billing reconciles against the
grant rows, so the customer is invoiced for seats nobody bought. We cannot reproduce it locally.

Make `app.webhooks:handle_webhook` idempotent on the event ID. Redelivering `evt_whk_88` must
leave `ws_acme` at exactly 4 seats, granted once, from the founder's single seat.
