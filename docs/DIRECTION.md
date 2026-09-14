# Direction

Written 2026-09-14, from the code at `10dfbee` (the nightly fix's last engine commit, pull request #25, merged as `5b216a1`), after the nightly's first real finding was
closed. Three independent drafts (one told to argue for A, one for B, one to find C), one cold
read of the kernel for day estimates, and one cold judge who installed the wheel and followed the
README literally, all fed this; the numbers below are theirs and are re-runnable. This is an
argument, not a roadmap. It ends in one recommendation and one probe.

## The honest limit today

The kernel judges one handler shape, a synchronous top-level `def handler(store, event)`, against
a store it owns (`CreditStore` or `InventoryStore`, four methods each), on a SQLite file in a
directory it made, in a fixed scenario: its schema, its seed, its event (`evt_1042`, `$25`, one
account). The GitHub Action is the product surface, and the cold judge got from a clean wheel to a
verdict in five seconds. To be judged, a user changes everything about their own code: the
function's signature and arity, every durable write (it must go through the store's methods, or
it is `raw-sql`, correct and unjudgeable), the schema (a dedup table of their own is `shadow-table`),
the event (they are judged on the fixture's payload, not theirs), and the branch layout (the fix
must live on a branch while the base stays at the contract's tree, which the README did not say
until the judge's seven stalls were fixed in #26). The cold judge's realistic
`apply_credit(conn, event)` produced a bare `AttributeError` at `check`, exit 2: `init` checks the
handler's shape (one top-level `def`, two positional parameters) and cannot see that the second one
is a connection, not the store. That is the limit: "your code" is not a thing this tool is pointed at; it is a thing you port into it.

Sizes: 14,414 source lines under `src/nemisis` without the fixtures and 634 tests at the merged
engine; from the cold read at `a0c4a9f`, before the fix added its pins, 43 pinned side-channel
shapes in `tests/test_verdict_paths.py`, 91 code lines that assume SQLite (47 of them in the kernel's four
files, in 11 functions and 6 constants), 13 places that assume the handler shape. `crashcheck.py`
and `crash_models.py` make no SQLite call of their own (`crashcheck.py` imports the runner and lists
the SQLite resources in the engine digest; `crash_models.py` names the slice in its docstring); the
store dependency's code lives in `sqlite_runner.py` (1,736 lines) and `scenario.py` (179 lines), behind the `Scenario` seam that
`sqlite-inventory-v1` proved (964 insertions, 22 files, zero runner lines).

## Direction A: bring your own store

What "bring your own store" means splits in two, and the split is the whole argument.

Step 1, a user scenario on the kernel's SQLite backend: open the registry (`SCENARIOS` is a
two-entry module literal, `src/nemisis/scenarios/__init__.py:10-13`), bind the user scenario's
bytes into `engine_code_digest` (today a fixed nineteen-name list of fifteen modules and four packaged
JSON files, `crashcheck.py:80-100`, so a foreign scenario would run unhashed and every receipt would misstate its engine), make the nine
packaged-resource fields of `Scenario` optional, seal `StoreBase._pause` and `_require` against a
subclass that commits without pausing (the commit report is the kill point), and lift `_next_rowid`
into the kernel (copied verbatim in both scenarios; a third author will get it wrong). Estimate: 2
days. Pinned shapes that come back: none; the probes, the world scan, the sweep, and the kill are
untouched.

Step 2, a backend the kernel did not create (Postgres, an HTTP store): a seam behind
`_seed_database`, `_read_only`, `_file_identity`, `_read_content`, `_HEADER_PRAGMAS` and the WAL
sidecar exemption (about 103 runner lines), a second implementation of "read the whole database"
(`pg_catalog` plus every row of every table in canonical order), a redteam vocabulary for it (five
grammar ops emit `sqlite3.connect(store._database)` today), and a rewrite of the alpha boundary in
`PRODUCT.md` and `SECURITY.md`, because a store the candidate's team wrote is a state probe the
candidate chose. Estimate: 10.5 more days by the advocate; the cold read says 40 for the whole of A
across 38 functions. Pinned shapes that come back: nine become unclaimable outright (the header
fields, the reserved bytes, bytes past the last page, the file flag, the extended attribute, the
mode and mtime of the file) and eight more stay closed only if a full catalog-and-row read is
rebuilt for the new backend. The riskiest assumption, named by the advocate against their own
case: that a buyer wants the kernel to kill a worker that talks to *their* server. `os.killpg` on
the client does not stage the crash the product sells; the server is untouched and may commit
after the worker dies. The evidence gets weaker exactly where it gets more expensive. An HTTP
store is worse and should not be scoped: "read the whole database after the kill" becomes "ask the
untrusted party what it holds".

## Direction B: one painful niche

Webhook and idempotency-key handlers are already what the kernel proves: `checkpoint_reached` is
"one durable effect plus its marker", which is the idempotency-key invariant, and both shipped
scenarios are that shape with different nouns. Stage 0 is a Stripe-shaped third scenario
(`sqlite-webhook-idempotency-v1`: key written before the effect, key retention sweep, same-key
redelivery, as zoo trees), which costs what the inventory scenario cost: 1.5 days, zero runner
lines, zero new false-pass surface. Everything after it is where the niche bites: un-pin the
target (`bind_anchor` refuses any target but the scenario's constant), declare the binding shape
instead of hardcoding `(store, event)` (measured: 1 of 11 realistic Flask, FastAPI, Celery and
class-based shapes binds today; FastAPI handlers are `async def`, which is refused outright), let
the app own the schema (which means `apply` can no longer predict every row and rowid, so
attribution degrades from the whole database to the tables the app declares), re-cut the header
pins so an ordinary insert-plus-delete commit is not an integrity failure (that alone reopens the
`freelist` shape, and a lazy mask reopens `header-reserved-byte`, `trailing-bytes` and `rowid`),
widen `_trusted_code` past the store class or write the ORM into the boundary (a module that
rebinds `Session.commit` at import is `patched-store-class` one level down), and make the worker's
import environment the app's venv. Estimate: 10 days by the advocate, 34 by the cold read across 24
functions. Riskiest assumption: that real handlers bend into a fixed, named-operation store
without a rewrite. The code argues against it: a handler that also writes a log line, an outbox
row through a second engine, or a Redis key forfeits its verdict on day one, for a reason that is
correct and unfixable at this altitude.

## Direction C: ship the map, not the verdict

The C-finder found this in the code: `_execute_sweep` already computes, on every `check`, a
complete crash-window map (one fresh world per store commit, killed there, replayed, with
`post_kill_snapshot` and `final_snapshot` per kill point) and throws it away behind a base tree, a
hunt, a capsule, and a fix. A verdict-free `nemisis map <tree>` needs 38 lines (the probe is
`docs/reports/2026-09-14-map-probe.py`; at the merged engine, `uv run python
docs/reports/2026-09-14-map-probe.py fixture:sqlite-credit-v1/<tree>` maps six of the nine credit
trees in under a second each with no base argument and refuses `raw-sql`, `shadow-table`, and
`tail-bytes` at the census with `INTEGRITY_ERROR`, the row a map must show, not hide), and its
output is the product:
`mark-first` maps to "commit 1 `mark_processed`: kill here leaves $0 marked done; the retry still
ends at $0". It sells information to the developer twenty minutes before the bug, instead of
judgment after the fix. Estimate: 4.5 days. Pinned shapes that come back: none, as long as a
census refusal degrades one row and never prints a clean map; 27 of the 28 side-channel shapes
block the census outright, and the pressure to "show the map anyway" is the one change that would
reopen all of them. Riskiest assumption, in the finder's own words: a developer will hand-port a
real handler to the store API to get a map of code they are still writing, when they demonstrably
will not port one to get a verdict on a bug they already fixed. The steady state is also boring:
the handler people should write makes one commit and maps to one row that says "safe".

## What the three have in common

Every riskiest assumption is the same wall: `(store, event)` against a store the kernel owns.
A's step 2 tries to move the store, B's stages 1 to 6 try to move the handler, C tries to change
what the wall buys. Nobody has measured the wall on a real handler. The cold judge measured it on
one and hit `AttributeError`.

## Recommendation

**Direction A, step 1 only: bring your own scenario, on the kernel's store.** Open the registry
so a scenario can live outside the package, bind its bytes into the engine digest, make the nine
packaged-resource fields optional, seal `_pause` and `_require`, lift `_next_rowid` into the
kernel. Two days. It is the only move on the table that widens what the kernel can judge without
reopening a single one of the 43 pinned shapes, because the probes, the world scan, the sweep,
and the kill are untouched; the buyer brings their bug shape and their vocabulary, and the kernel
keeps its store, its file, and its attribution. Direction B's stage 0, the Stripe-shaped webhook
scenario, is then the first scenario shipped through that door rather than a fork of the package:
the two compose, and B's stages 1 to 6 (bind a framework signature, let the app own the schema,
relax the header pins) stay unbuilt, because each of them reopens a pinned shape. Direction C,
the map, is kept as the second output of the same kernel if the probe below says the seam is
usable by a stranger: it is 38 lines behind the seam and loses nothing, but it has no buyer yet
and the same wall. Direction A's step 2, a backend the kernel did not create, is rejected on the
advocate's own evidence: the kill stops staging the crash the product sells, nine shapes become
unclaimable, and the redteam covers none of the new path.

Why not stop here: the kernel is now red-teamed by a machine that found what three hostile
rounds did not, and it found it in the reading schedule, not in the attribution. That is a kernel
worth pointing at more than two bug shapes. But the door is closed today: a stranger cannot
register a scenario without editing the installed package, and if they did, its bytes would not
be in the engine digest. Opening that door costs two days and no claims.

## The probe

The riskiest assumption of the recommendation is that a person who has not read
`sqlite_runner.py` can write a `Scenario` at all: forty-two fields, of which `apply` must predict
every row of every seeded table including rowids, bit-exactly, or every commit is an integrity
failure. The probe: write one scenario module outside the package, a third bug shape with its own
schema, seed, store subclassing `StoreBase` and calling `_pause` after each commit, its own
`tables`, `apply`, `snapshot`, and `checkpoint_reached`; monkeypatch it into `SCENARIOS` from one
test file under `tests/`; run `check` against a buggy tree and an atomic tree for it; do not touch
the kernel. Measure four things: how many of the forty-two fields could be filled without opening
the runner; whether `apply` was right the first time or how many integrity failures it took;
what `engine_code_digest` does with a foreign scenario (it ignores it, which is the false
provenance the two days must fix); and the wall-clock from a blank file to the first verdict.
Kill criteria: if `apply` cannot be written without reading `_attributed_probe`, the seam is an
internal API and the two days become six; if the whole probe takes a stranger more than a
working day, the door is not worth opening and the honest product is the GitHub Action on the
two shipped scenarios, with the README rewritten to say so.

It fits in one night behind the existing seam, with tests, touches no verdict semantics, and
claims nothing (`FIXTURE`/`LOCAL` only, never a product). It was not built tonight: §3 closed late, because the nightly's fix took five revisions under
four rounds of hostile review (the read the nightly found; what the garbage collector opened; the
read after the exit; the store's own audit; a temporary schema object), and a probe built on an
engine still under review would have been a guess. What it costs: one night for one person or
one subagent, no kernel change, one test file; the four measurements above are its output, and
the two kill criteria decide the recommendation without further argument.

## What stopping here leaves

A verified local alpha with a red-teamed kernel (the nightly now catches what three hostile rounds
did not), a GitHub Action, a release, and a README whose "Point it at your code" section promises
more than the five preceding sections prove. If this stops here, nothing is owed: the four README
changes the cold judge's stalls asked for (the install line at the top, the fixture path in
`propose-patch`, the branch rule for `--base main --candidate HEAD`, and the sentence that says
what the judge learned the hard way) merged in #26.

---

## Postscript, 2026-09-15: the riskiest assumption, tested against an agent

The memo's riskiest assumption was that a developer would hand-port a real handler to a four-method
store to earn a receipt. That was tested — not against a developer, against an AI coding agent. A
fresh headless Claude Code session, given the Nemisis MCP server, the skill, an issue, and one
instruction, wrote the port, mapped the crash windows, hit `EVIDENCE_INCOMPLETE`, read the remedy,
fixed the port, reached `FIX_PROVEN_FOR_THIS_CAPSULE`, and applied the fix to the real handler — no
human input ([the write-up and the committed tool log and receipt](reports/2026-09-15-agent-demo.md)). The wall the memo found was real;
it was the wrong customer standing in front of it. For an agent, the port is a five-minute subtask,
so Direction A's step 1 shipped tonight as the agent surface (the `mcp` server, `map`, the skill),
not as a human "bring your own scenario" door. The memo's day estimates for A's later steps stand;
what changed is who the door is for.
