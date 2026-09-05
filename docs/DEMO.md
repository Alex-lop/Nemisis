# 90-second demo

Five commands, one story: the agent's retry patch is green, and the money still moves twice. Every
expected output below is pasted from a real local run of this tree; the screenshots and GIF it
points at live in [`docs/assets/screenshots/`](assets/screenshots/) and were captured from the same
commands. The longer three-minute cut with fallbacks is [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

## The pitch, one paragraph (say this first)

AI coding agents ship retry patches that look green and still double-charge in production: the
existing test passes, a "call it twice" check passes, and the bug only appears when a worker dies
between the credit and the marker that says the credit happened. CrashCheck is a crash-test dummy
for those patches. It runs the handler in a real worker, waits until the `$25` credit is durably on
disk, kills the whole process group with `SIGKILL`, confirms the worker is dead, starts a fresh
worker, and delivers the byte-identical event again. Then it reads the SQLite file through an
independent read-only connection. The agent's patch ends at `$50`; the real fix ends at `$25`. The
verdict comes from the database and the process receipts, never from the model that wrote the
patch, and the crash is frozen into a capsule that the next patch has to beat too.

## Pre-flight (before the clock starts)

```bash
uv sync --frozen --dev
uv run nemisis doctor --mode local          # expect: NEMISIS DOCTOR — LOCAL READY
rm -rf .nemisis/runs .nemisis/repros
clear
```

Terminal at 17 pt or larger, about 140 columns, dark theme. Run from the repository root so every
printed path is relative (`.nemisis/…`) and no home directory appears on screen.

## The script

| Clock | Type | Judge sees | Say | Visual aid if the terminal fails |
| --- | --- | --- | --- | --- |
| 0:00 | `sed -n '/^def apply_credit/,$p' src/nemisis/fixtures/sqlite_credit_v1/trees/misleading-green/app/credits.py` | Just the handler, four statements: `if processed: return`, `credit(...)`, `mark_processed(...)` | "A bug report says retries sometimes credit an order twice. An agent rewrote the handler. Its test is green. Check, credit, mark: the crash window is between those last two lines, and the rewrite did not move it." | none needed |
| 0:15 | `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/misleading-green --corrected fixture:sqlite-credit-v1/atomic --mode local` | about two seconds later, `verdict: PATCH_FAILED_STILL_REPRODUCES` and `timeline: $25.00 durable -> SIGKILL -> fresh worker -> $50.00`; exit `1` | "Worker starts. Twenty-five dollars hits disk. SIGKILL to the process group. Confirmed dead. Fresh worker, same event. Fifty dollars. Five fresh worlds, five times." | [`terminal-check-misleading-green.png`](assets/screenshots/terminal-check-misleading-green.png) |
| 0:40 | `CAP=$(ls .nemisis/repros/double-credit/*/capsule.json)` then `uv run nemisis replay "$CAP" --source fixture:sqlite-credit-v1/buggy --role base --mode local` | `verdict: BUG_REPRODUCED`; exit `1` | "The crash is now a frozen capsule. Same capsule against the original handler: same guard, same crash window, same fifty dollars." | [`crashcheck-demo.gif`](assets/screenshots/crashcheck-demo.gif), first beat |
| 0:55 | `uv run nemisis replay "$CAP" --source fixture:sqlite-credit-v1/atomic --role corrected --mode local` | `verdict: FIX_PROVEN_FOR_THIS_CAPSULE`, `timeline: $25.00 durable -> SIGKILL -> fresh worker -> $25.00`; exit `0` | "Same kill, same retry, against an atomic fix. Twenty-five dollars, one ledger row, one marker. Exit zero. This is the regression test that ships with the repro." | [`terminal-replay-atomic-proven.png`](assets/screenshots/terminal-replay-atomic-proven.png) |
| 1:15 | `open .nemisis/runs/$(ls -t .nemisis/runs \| head -1)/report.html` (macOS) or paste the printed `report:` path into a browser | Green report: **Fix proven for this capsule only**, `$25.00 vs $25.00`, capsule and engine digests | "Everything you just saw is a receipt: process ids, exit code minus nine, two worker nonces, database snapshots, source tree digests. No model confidence anywhere. What is proven is narrow on purpose: this exact tree beat this exact capsule." | [`report-fix-proven.png`](assets/screenshots/report-fix-proven.png) and the failing twin [`report-patch-failed.png`](assets/screenshots/report-patch-failed.png) |
| 1:30 | stop | | | |

## Expected output, verbatim

`check` (the `capsule digest`, run id, and tree digests are the values your run prints; the
verdict, summary, hypotheses, control, and timeline lines are exact):

```text
NEMISIS CRASHCHECK — LOCAL
execution: COMPLETED
integrity: VALID
verdict: PATCH_FAILED_STILL_REPRODUCES
summary: The candidate replayed evt_1042 to a durable +$50 duplicate effect.
capsule digest: <64 hex digits>
engine code digest: <64 hex digits, pinned in docs/STATUS.md>
engine source commit: <the commit you ran at>
hypotheses: 2 run -> selected effect-commit (effect-commit-v1)
control: base delivered the event twice with no kill in 2/2 fresh worlds and ended exactly once; the duplicate needs the crash
timeline: $25.00 durable -> SIGKILL -> fresh worker -> $50.00
```

`replay … --source fixture:sqlite-credit-v1/buggy --role base`:

```text
verdict: BUG_REPRODUCED
summary: The base replayed evt_1042 to a durable +$50 duplicate effect.
```

`replay … --source fixture:sqlite-credit-v1/atomic --role corrected`:

```text
verdict: FIX_PROVEN_FOR_THIS_CAPSULE
summary: Five fresh worlds ended at exactly +$25, one ledger effect, and one marker.
timeline: $25.00 durable -> SIGKILL -> fresh worker -> $25.00
```

Exit codes are `1`, `1`, `0`. If anything else appears, read the `summary:` line aloud; it names
the missing receipt, and the run is `EVIDENCE_INCOMPLETE` rather than a verdict.

## If you have a Token Factory key

Insert one beat before `check`, at about 0:12, and pass `--scenario .nemisis/config.json` to the
`check` command:

```bash
uv run nemisis init --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --target app.credits:apply_credit --base fixture:sqlite-credit-v1/buggy \
  --scenario sqlite-credit-v1 --nemotron
```

Point at the `nemotron: … · LIVE · …` line and say: "Nemotron on Nebius Token Factory read the bug
report and the base handler, never the patch, and proposed the contract. Our code checked it
against the audited catalog. The model proposes; it never decides." The exact success and failure
shapes are in [LIVE_SETUP.md](LIVE_SETUP.md). Without a key the command exits `2` and drafts
nothing; say "fail closed" and continue. Never show a `MOCKED` receipt as live.

## Fallbacks

- **`check` prints `EVIDENCE_INCOMPLETE`.** Read the `summary:` line, then show the committed
  evidence instead: `uv run python -m http.server 8000 --bind 127.0.0.1`, open
  <http://127.0.0.1:8000/docs/assets/crashcheck-hero/>, press **Replay fixture evidence**. Say that
  this is the committed `LOCAL` / `FIXTURE` receipt bound to an earlier exact commit. Screenshots:
  [`viewer-01-initial.png`](assets/screenshots/viewer-01-initial.png),
  [`viewer-02-mid-replay.png`](assets/screenshots/viewer-02-mid-replay.png),
  [`viewer-03-verdict-receipt.png`](assets/screenshots/viewer-03-verdict-receipt.png).
- **No browser.** Skip 1:15; the terminal verdicts carry the story.
- **Stale `.nemisis/`.** `rm -rf .nemisis/runs .nemisis/repros` and start again from 0:15.
- **Nothing runs.** Play [`crashcheck-demo.gif`](assets/screenshots/crashcheck-demo.gif) (30 s,
  buggy → agent's patch → atomic fix) and narrate over it.
