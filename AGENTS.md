# Agent instructions

If you are an AI coding agent with the Nemisis MCP server attached (`claude mcp add nemisis -- uvx
--from nemisis nemisis mcp`, or `nemisis mcp` over stdio from a checkout), use it to prove a
crash-safety fix the way a human cannot be bothered to.

## When

You are fixing a bug where a crash or restart between an effect and its "processed" marker lets a
retry apply the effect twice — a double credit, a double reservation, a double send, a
non-idempotent webhook. A green unit test does not prove the race is closed. Nemisis kills the
handler at every store commit and checks the retry lands the effect exactly once.

## How

1. `list_scenarios` — pick the shape that matches the bug (`sqlite-credit-v1`: one effect plus its
   marker; `sqlite-inventory-v1`: a decrement plus its marker).
2. `port_template(scenario)` — write `.nemisis/port/<scenario>/app/<file>.py`, one handler
   mirroring the real one, through the store's methods only.
3. `map(candidate, scenario)` — see the crash windows before you fix.
4. `check(candidate, scenario)` — iterate to `FIX_PROVEN_FOR_THIS_CAPSULE`. `EVIDENCE_INCOMPLETE`
   is never a pass: it means the port wrote around the store; read the remedy and use the store,
   never edit the kernel.
5. Apply the same change to the real handler. Attach the receipt and a **port ledger** to the PR:
   which real lines map to which store calls, and what the port does not carry. Say what the
   receipt proves and what it does not.

The kernel never calls a model. `draft_contract` and `propose_patch` are the only model calls and
are `BLOCKED` without a Token Factory key. Everything runs locally; nothing is uploaded.
