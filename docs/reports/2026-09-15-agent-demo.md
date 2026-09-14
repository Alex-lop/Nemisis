# An agent proves a retry fix, unaided — 2026-09-14

The one thing that had to be true by morning: a coding agent, handed a repository with a retry bug
and the Nemisis MCP server, reaches `FIX_PROVEN_FOR_THIS_CAPSULE` with no human input and attaches
the receipt. It is true. A fresh, headless Claude Code session — no memory of this project, one
instruction, the skill, and the server — did it. The evidence is committed beside this file, not
narrated: the receipt (`2026-09-15-agent-demo-credit-capsule.json`) and the distilled tool log
(`2026-09-15-agent-demo-credit-toollog.txt`, extracted from the run's stream-json transcript).

## Run 1 — `sqlite-credit-v1`, unaided, 14 turns

The scratch repository was the buggy credit handler (`app/credits.py`) plus its bug report
(`issue.md`) and the Nemisis skill; nothing else. One instruction, then no human input. The tool
log shows exactly what the agent did, in order:

1. read `issue.md` and `app/credits.py` to orient;
2. `list_scenarios` (MCP), picked `sqlite-credit-v1`;
3. `port_template(sqlite-credit-v1)` (MCP);
4. wrote a port at `.nemisis/port/sqlite-credit-v1/app/credits.py`;
5. `map(.nemisis/port/sqlite-credit-v1)` (MCP) — the crash-window map;
6. refined the port;
7. `check(.nemisis/port/sqlite-credit-v1)` (MCP) → `FIX_PROVEN_FOR_THIS_CAPSULE`, exit 0;
8. applied the same change to the real `app/credits.py`.

It mixed the MCP tools with plain shell (writing the port with `cat >`, reading the check result
with `jq`); the tool log records both. Its own closing words, verbatim from the transcript:

> The handler did `credit` then `mark_processed` as two separate commits. The crash map showed the
> dangerous window: killed after `credit`, the retry sees no marker and credits again, leaving
> acct_7 at $50. The fix in `app/credits.py`: replace the two calls with the store's atomic
> `credit_and_mark`, so the credit and its marker land in one transaction. The processed check
> stays as the retry guard.

The receipt beside this file is a real capsule for `sqlite-credit-v1` at the current engine
(`1afdb6ee…`). This run reached the proof directly; it did not hit `EVIDENCE_INCOMPLETE` on the way
(an earlier draft of this report claimed it did — that was a misread of the port template's forfeit
list, corrected here).

## Run 2 — `sqlite-inventory-v1`, unaided, transcript truncated

Same setup with the buggy inventory handler. The agent again drove `list_scenarios`,
`port_template`, `map`, and `check`, reached `FIX_PROVEN_FOR_THIS_CAPSULE`, wrote a receipt under
`.nemisis/repros/double-reservation/…/capsule.json`, and applied the atomic `reserve_and_mark` fix
to `app/inventory.py`. The headless wrapper process was cut before it emitted its final summary
line (the machine was low on memory, the pressure that killed several background tasks that night),
so its transcript ends mid-stream and is not committed. The fixed handler and the receipt were on
disk in the scratch run; the closing narration is not, so this run is reported as partial, not
quoted.

## Reproduce

The bug report is packaged but `export` does not copy it, so build the scratch repo from the
checkout's fixture tree and issue directly:

```bash
NEM=/path/to/Nemisis                       # your Nemisis checkout
mkdir demo && cd demo && git init -q
mkdir -p app .claude/skills/nemisis
cp "$NEM"/src/nemisis/fixtures/sqlite_credit_v1/trees/buggy/app/credits.py app/credits.py
cp "$NEM"/src/nemisis/fixtures/sqlite_credit_v1/issue.md issue.md
cp "$NEM"/skills/nemisis/SKILL.md .claude/skills/nemisis/SKILL.md
git add -A && git commit -q -m "the buggy handler and its bug report"

claude mcp add nemisis -- uv run --project "$NEM" nemisis mcp
claude -p "Fix the double-credit-on-retry bug in app/credits.py and prove it is crash-safe with the nemisis MCP tools. Do not stop until check returns FIX_PROVEN_FOR_THIS_CAPSULE."
```

The kernel the agent drove never called a model; the whole loop is local and deterministic. What
the agent could not do — and the skill forbids — is edit the kernel to turn `EVIDENCE_INCOMPLETE`
into a pass; it fixes its port instead, which is the point.
