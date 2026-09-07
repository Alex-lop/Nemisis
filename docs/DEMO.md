# Two-and-a-half-minute demo

Eight commands, one story: the agent's retry patch is green, and the money still moves twice. The
expected output below was pasted from a local run of this tree. No test regenerates it, so re-run
the commands if a line reads differently. The screenshots and GIF live in
[`docs/assets/screenshots/`](assets/screenshots/); the 0:15, 0:40, and 0:55 aids were captured from
those exact commands, and the 1:15 and 2:05 aids are the nearest committed renders of a different
run. The longer four-minute cut with fallbacks is [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

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

Terminal at 17 pt or larger, about 140 columns, dark theme. Run from the repository root so
`check` and `replay` print relative paths (`.nemisis/…`). The optional `init` beat below prints its
`config:` path in full, so record from a checkout outside your home directory if you use it.

## The script

| Clock | Type | Judge sees | Say | Visual aid if the terminal fails |
| --- | --- | --- | --- | --- |
| 0:00 | `sed -n '/^def apply_credit/,$p' src/nemisis/fixtures/sqlite_credit_v1/trees/misleading-green/app/credits.py` | Just the handler, four statements: `if processed: return`, `credit(...)`, `mark_processed(...)` | "A bug report says retries sometimes credit an order twice. An agent rewrote the handler. Its test is green. Check, credit, mark: the crash window is between those last two lines, and the rewrite did not move it." | none needed |
| 0:15 | `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/misleading-green --corrected fixture:sqlite-credit-v1/atomic --mode local` | about three seconds later, `verdict: PATCH_FAILED_STILL_REPRODUCES` and `timeline: $25.00 durable -> SIGKILL -> fresh worker -> $50.00`; exit `1` | "Worker starts. Twenty-five dollars hits disk. SIGKILL to the process group. Confirmed dead. Fresh worker, same event. Fifty dollars. Five fresh worlds, five times." | [`terminal-check-misleading-green.png`](assets/screenshots/terminal-check-misleading-green.png) |
| 0:40 | `CAP=$(ls .nemisis/repros/double-credit/*/capsule.json)` then `uv run nemisis replay "$CAP" --source fixture:sqlite-credit-v1/buggy --role base --mode local` | `verdict: BUG_REPRODUCED`; exit `1` | "The crash is now a frozen capsule. Same capsule against the original handler: same guard, same crash window, same fifty dollars." | [`crashcheck-demo.gif`](assets/screenshots/crashcheck-demo.gif), first beat |
| 0:55 | `uv run nemisis replay "$CAP" --source fixture:sqlite-credit-v1/atomic --role corrected --mode local` | `verdict: FIX_PROVEN_FOR_THIS_CAPSULE`, `timeline: $25.00 durable -> SIGKILL -> fresh worker -> $25.00`; exit `0` | "Same kill, same retry, against an atomic fix. Twenty-five dollars, one ledger row, one marker. Exit zero. This is the regression test that ships with the repro." | [`terminal-replay-atomic-proven.png`](assets/screenshots/terminal-replay-atomic-proven.png) |
| 1:15 | `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/mark-first --mode local` | `verdict: PATCH_FAILED_INVARIANT_BROKEN`; `timeline: $0.00 durable (after commit 1) -> SIGKILL -> fresh worker -> $0.00`; exit `1` | "One more patch. This one passes the unit test, passes call-it-twice, and passes the same kill the original failed. So CrashCheck kills it once after every commit it makes. Killed after the marker, before the credit: zero dollars, marked done. The customer never gets paid. A checker that only killed in one place would have blessed this." | [`crashcheck-demo.gif`](assets/screenshots/crashcheck-demo.gif) |
| 1:35 | `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/raw-sql --mode local` | about two seconds later, `execution: CHECKPOINT_NOT_REACHED`, `verdict: EVIDENCE_INCOMPLETE`, and a summary that names `store.credit_and_mark(account_id, event_id, amount_cents)`; exit `2` | "This is the textbook fix, written as one raw SQL transaction on the store's own database. It is correct, and it gets no verdict. Kill points are store commits; the store made none, so there is nowhere to put the crash. CrashCheck names the write it saw and the store call that expresses the same fix. Exit two: not a pass and not a fail." | none needed |
| 1:50 | `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/shadow-table --mode local` | about four seconds later, `execution: INTEGRITY_ERROR`, `integrity: INVALID`, `verdict: EVIDENCE_INCOMPLETE`, and a summary that says "the schema changed"; exit `2` | "This one hides its dedup flag in a table it creates inside the store's own database. An earlier engine blessed it. The whole database is now compared with what the reported commits predict, so the extra table is seen and the verdict is forfeited instead of guessed." | none needed |
| 2:05 | `open .nemisis/runs/$(ls -t .nemisis/runs \| head -1)/report.html` (macOS) or paste the printed `report:` path into a browser | Report: verdict card, commit sweep table with the failing kill point, capsule and engine digests | "Everything you just saw is a receipt: process ids, exit code minus nine, two worker nonces, database snapshots, source tree digests. No model confidence anywhere. What is proven is narrow on purpose: this exact tree beat this exact capsule and every kill point of its own." | [`report-fix-proven.png`](assets/screenshots/report-fix-proven.png) and the failing twin [`report-patch-failed.png`](assets/screenshots/report-patch-failed.png) |
| 2:25 | stop | | | |

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
sweep: corrected makes 1 store commit (credit_and_mark); killed after each: #1 -> $25.00 EXACTLY_ONCE -> EXACTLY_ONCE
timeline: $25.00 durable -> SIGKILL -> fresh worker -> $50.00
```

The candidate is not swept because its boundary worlds already failed; only claimed fixes whose
five boundary worlds pass are killed once after each of their store commits.

`check … --candidate fixture:sqlite-credit-v1/raw-sql` (the whole `summary:` line, on one line in
the terminal):

```text
execution: CHECKPOINT_NOT_REACHED
integrity: INVALID
verdict: EVIDENCE_INCOMPLETE
summary: 5 of 5 candidate worlds did not complete: the handler changed the database without a single CreditStore commit (this event now shows balance $25.00, 1 credit row(s), 1 marker), so that write went through a connection CrashCheck does not own and no kill point exists inside that write. Kill points are store commits, so a write the store did not make has no kill point and earns no verdict. Express the same fix through the store: store.credit_and_mark(account_id, event_id, amount_cents) commits the credit and its marker together in one durable transaction; store.processed(event_id), store.credit(...), and store.mark_processed(event_id) are the three-step form; see docs/PRODUCT.md#the-store-api. No verdict is issued from incomplete or contradictory evidence.
sweep: candidate makes 0 store commits (none observed); killed after each: census incomplete -> NOT_OBSERVED
```

`check … --candidate fixture:sqlite-credit-v1/shadow-table`:

```text
execution: INTEGRITY_ERROR
integrity: INVALID
verdict: EVIDENCE_INCOMPLETE
summary: 5 of 5 candidate worlds did not complete: the durable change after credit_and_mark was not only the one credit_and_mark makes: the schema changed (a table, index, or trigger this scenario did not seed); the database header changed (PRAGMA user_version or application_id); something wrote around the trusted store. Kill points are store commits, so a write the store did not make has no kill point and earns no verdict. Express the same fix through the store: store.credit_and_mark(account_id, event_id, amount_cents) commits the credit and its marker together in one durable transaction; store.processed(event_id), store.credit(...), and store.mark_processed(event_id) are the three-step form; see docs/PRODUCT.md#the-store-api. No verdict is issued from incomplete or contradictory evidence.
```

Both exit `2`. `EVIDENCE_INCOMPLETE` is the third answer the tool is allowed to give, and the
only honest one when the kill could not be placed where the money moved.

`replay … --source fixture:sqlite-credit-v1/buggy --role base`:

```text
verdict: BUG_REPRODUCED
summary: The base replayed evt_1042 to a durable +$50 duplicate effect.
```

`replay … --source fixture:sqlite-credit-v1/atomic --role corrected`:

```text
verdict: FIX_PROVEN_FOR_THIS_CAPSULE
summary: Five fresh worlds ended at exactly +$25, one ledger effect, and one marker. The commit sweep killed the corrected once after each of its 1 store commit (credit_and_mark) and every replay ended exactly once.
sweep: corrected makes 1 store commit (credit_and_mark); killed after each: #1 -> $25.00 EXACTLY_ONCE -> EXACTLY_ONCE
timeline: $25.00 durable -> SIGKILL -> fresh worker -> $25.00
```

Exit codes are `1`, `1`, `0`. If anything else appears, read the `summary:` line aloud; it names
the missing receipt, and the run is `EVIDENCE_INCOMPLETE` rather than a verdict.

## The second scenario, one line

The same engine, a different subject. If a judge asks whether this only knows about money:

```bash
uv run nemisis check --base fixture:sqlite-inventory-v1/buggy \
  --candidate fixture:sqlite-inventory-v1/mark-first --mode local
```

About four seconds, `verdict: PATCH_FAILED_INVARIANT_BROKEN`, exit `1`:

```text
summary: Killed after store commit 1 of 2 (mark_reserved) and replayed: 10 units on hand instead of 8 units (0 reservation rows, 1 marker): order-1 was marked reserved but nothing was reserved, so the order is unfilled. The 5 capsule-boundary worlds passed, so this is a crash window the base did not have.
sweep: candidate makes 2 store commits (mark_reserved, reserve); killed after each: #1 -> 10 units INVARIANT_FAILED, #2 -> 8 units EXACTLY_ONCE -> INVARIANT_FAILED
timeline: 10 units durable (after commit 1) -> SIGKILL -> fresh worker -> 10 units
```

Same kill, same sweep, same verdict vocabulary; the effect runs the other way and the units are
stock, not dollars.

## The closing beat: the generator

Run this while you answer questions; it takes about eighty seconds.

```bash
uv run nemisis redteam --cases 30 --seed 3 --out ./redteam
```

It renders thirty handlers from a grammar over store operations and the writes around the store
that hostile reviews wrote by hand, runs `check` on each, and compares every verdict with an
oracle computed from the operation sequence alone. It prints one row per case and then its last
two lines:

```text
generated 30 handlers from seed 3; 0 disagreements
handlers and evidence: <the absolute path of ./redteam>
```

Exit `0`. Say: "The checker is not trusted because we wrote it carefully; it is trusted because a
generator writes handlers it has never seen and an independent oracle grades the grades. One
disagreement is exit one and an issue." The nightly workflow runs three hundred per scenario.

## If you have a Token Factory key

The strongest beat: let NVIDIA's model write the patch, then crash-test it. Insert it at about
0:12, before the packaged `check`:

```bash
uv run nemisis propose-patch --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --base fixture:sqlite-credit-v1/buggy --out ./nemotron-candidate
uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate ./nemotron-candidate --mode local
```

Point at the `nemotron: … · LIVE · …` line and say: "Nemotron on Nebius Token Factory read the bug
report and the buggy module, nothing about how we kill or judge, and wrote this patch. Now we crash
it." Whatever verdict comes back is the demo: a proven fix shows the checker blessing a real AI
patch, a failing one shows exactly why the tool exists. Without a key the command exits `2` and
writes nothing; say "fail closed" and continue with the packaged candidates.

The smaller model beat is the contract proposal. Insert it before `check` and pass
`--scenario .nemisis/config.json` to the `check` command:

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
- **No browser.** Skip the 2:05 report beat; the terminal verdicts carry the story.
- **Stale `.nemisis/`.** `rm -rf .nemisis/runs .nemisis/repros` and start again from 0:15.
- **Nothing runs.** Play [`crashcheck-demo.gif`](assets/screenshots/crashcheck-demo.gif) (33 s,
  buggy → agent's patch → atomic fix) and narrate over it.
