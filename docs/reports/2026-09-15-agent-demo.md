# An agent proves a retry fix, unaided — 2026-09-14

The one thing that had to be true by morning: a coding agent, handed a repository with a retry bug
and the Nemisis MCP server, reaches `FIX_PROVEN_FOR_THIS_CAPSULE` with no human input and attaches
the receipt. It is true. A fresh, headless Claude Code session — no memory of this project, one
instruction, the skill, and the server — did it twice.

## Run 1 — `sqlite-credit-v1`, unaided, complete

The scratch repository was the buggy credit handler (`app/credits.py`) plus its bug report
(`issue.md`) and the Nemisis skill; nothing else. One instruction, then no human input.

**Tool sequence (14 turns):**
`list_scenarios` → `port_template(sqlite-credit-v1)` → `map(port)` → `check(port)` →
`EVIDENCE_INCOMPLETE` → (read the remedy, rewrote the port through the store) → `check(port)` →
`FIX_PROVEN_FOR_THIS_CAPSULE` (exit 0) → applied the same change to `app/credits.py`.

The agent's own words at the end:

> The handler did `credit` then `mark_processed` as two separate commits. The crash map showed the
> dangerous window: killed after `credit`, the retry sees no marker and credits again, leaving
> acct_7 at $50. The fix in `app/credits.py:27`: replace the two calls with the store's atomic
> `credit_and_mark`, so the credit and its marker land in one transaction.

The receipt is a real capsule under the repo's `.nemisis/repros/double-credit/…/capsule.json`; the
run is `local-…`. The agent hit `EVIDENCE_INCOMPLETE` first — its first port wrote around the store
— read the remedy the tool returned, and fixed the port rather than the kernel. That is the loop
working exactly as designed.

## Run 2 — `sqlite-inventory-v1`, unaided, transcript truncated

Same setup with the buggy inventory handler. The agent again drove `list_scenarios` →
`port_template` → `map` → `check`, reached `FIX_PROVEN_FOR_THIS_CAPSULE`, wrote the receipt
(`.nemisis/repros/double-reservation/…/capsule.json`), and applied the atomic `reserve_and_mark`
fix to `app/inventory.py`. The headless wrapper process was cut before it emitted its final
summary line (the machine was low on memory, the same pressure that killed several background
tasks tonight), so the transcript ends mid-stream. The proof and the fixed handler are on disk; the
closing narration is not. This run needed no human hand — only its transcript capture was
incomplete.

## Reproduce

```bash
# a scratch repo with the buggy handler and its issue
mkdir demo && cd demo && git init -q
uv run --project <nemisis-checkout> nemisis export fixture:sqlite-credit-v1/buggy .   # or copy the tree
cp <nemisis-checkout>/skills/nemisis/SKILL.md .claude/skills/nemisis/SKILL.md

# register the server (published form once 0.2.1 ships the mcp extra)
claude mcp add nemisis -- uvx --from nemisis nemisis mcp
# or, from a local checkout:
claude mcp add nemisis -- uv run --project <nemisis-checkout> nemisis mcp

# be the customer
claude -p "Fix the double-credit-on-retry bug in app/credits.py and prove it is crash-safe with the nemisis MCP tools. Do not stop until check returns FIX_PROVEN_FOR_THIS_CAPSULE."
```

The kernel the agent drove never called a model; the whole loop is local and deterministic. What
the agent could not do — and the skill forbids — is edit the kernel to turn `EVIDENCE_INCOMPLETE`
into a pass. It read the remedy and changed its port, which is the point.
