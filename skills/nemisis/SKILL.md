---
name: nemisis
description: Use when you are fixing a retry, replay, duplicate-delivery, or idempotency bug and want to prove the fix is crash-safe. Nemisis kills the handler at every store commit and checks that a retry lands the effect exactly once, then hands back a receipt you attach to the PR.
---

# Prove your retry fix with Nemisis

You are fixing a bug where a crash between an effect and its "done" marker lets a retry double the
effect (a webhook credited twice, an order reserved twice, an email sent twice). A passing unit
test does not prove the crash is gone. Nemisis does: it kills the handler at every store commit and
checks that a fresh retry ends with the effect exactly once. Use it whenever the bug is about
retries, replays, duplicate delivery, or idempotency.

You do not change Nemisis and you do not restructure the user's code. You write a **port**: a
minimal handler against Nemisis's store that mirrors the real handler's logic, iterate on the port
until it is proven, then apply the same change to the real handler.

## The loop

1. **`list_scenarios`.** Pick the shape that matches the bug. One durable effect plus its marker is
   `sqlite-credit-v1`. A decrement with a marker is `sqlite-inventory-v1`. The tool names each
   store's methods and its one-sentence invariant.
2. **`port_template(scenario)`.** It returns the handler skeleton, the store API, and the three
   shapes that forfeit a verdict. Write `.nemisis/port/<scenario>/app/<file>.py` with the one
   handler function, its logic mirroring the real one, expressed through the store's methods.
3. **`map(candidate=".nemisis/port/<scenario>", scenario)`.** See where the handler can die before
   you fix it: each store commit, the durable state a crash there leaves, and the state after the
   retry. This tells you which commit boundary is the dangerous one.
4. **`check(candidate=".nemisis/port/<scenario>", scenario)`.** Iterate until the verdict is
   `FIX_PROVEN_FOR_THIS_CAPSULE` (exit 0). The other verdicts are not passes:
   - `PATCH_FAILED_STILL_REPRODUCES` / `PATCH_FAILED_INVARIANT_BROKEN`: the port still has a bug.
   - `EVIDENCE_INCOMPLETE`: the port wrote **around** the store (raw SQL on the connection, a dedup
     table of its own, a file beside the database). Read the `summary`'s remedy and express the fix
     through the store's methods instead. Never change the kernel to make this go away.
5. **Apply the same change to the real handler.** Then fill in the **port ledger** and attach it to
   the PR beside the receipt: which lines of the real handler map to which store calls, and what
   the port does **not** carry (a log line, a second datastore, a Redis key). The receipt proves the
   port; you are responsible for the correspondence, and the ledger is where you state it. A receipt
   without a ledger is a claim above its evidence.

## The port ledger (paste into the PR)

```
Nemisis port ledger — <scenario>, verdict FIX_PROVEN_FOR_THIS_CAPSULE, run <run_id>
  real handler line -> store call:
    <path>:<line>  credit + insert marker  ->  store.credit_and_mark(...)
  the port does not carry:
    - <the log line / metric / second write the real handler also does>
  receipt: <receipt_resource>
```

## What the receipt does and does not prove

It proves that the ported handler, killed at every store commit and retried, lands the effect
exactly once against the scenario's store. It does not prove anything the port did not carry, and
it says so. The kernel never calls a model; `draft_contract` and `propose_patch` do, and they are
`BLOCKED` without a Token Factory key, never mocked. Everything runs on your machine, on your
checkout, and nothing is uploaded.
