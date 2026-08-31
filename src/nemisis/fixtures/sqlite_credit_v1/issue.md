# Duplicate account credit after retry

A timeout followed by a retry occasionally applies the same order credit twice.
We cannot reproduce it locally.

Make `app.credits:apply_credit` idempotent by event ID. Retrying `evt_1042` must
leave account `acct_7` credited exactly $25 once.
