# How it works

The README is the thirty-second version. This is the machinery behind it: how CrashCheck reaches a
verdict, how it was red-teamed, how you point it at your own code, and the two scenarios it judges.

## The check, step by step

CrashCheck runs the exact patch in a real worker process and treats every durable write as a place
the process could die.

1. **Hunt on the base.** Two fixed kill points are tried on the buggy tree before the candidate is
   even read; the one that reproduces the duplicate is frozen into a content-addressed capsule.
2. **No-crash control.** The base is delivered the same event twice with no kill. It ends exactly
   once, so the duplicate needs the crash: this is a crash/retry bug, not a broken handler.
3. **Kill, restart, replay.** Five fresh worlds per tree. Each seeds a database, waits until the
   credit is durably committed, `SIGKILL`s the whole process group, confirms exit `-9`, starts a
   fresh worker, replays the byte-identical event, and reads the database through an independent
   read-only connection.
4. **Sweep every commit of a claimed fix.** A patch that passes step 3 is then killed once after
   *each* store commit it makes. A handler that marks first and credits second passes step 3 and
   loses the credit here.
5. **Decide from durable state and process receipts.** Balance, ledger rows, marker count, PIDs,
   exit codes, worker nonces, tree digests. Five worlds must agree or there is no verdict.

| Exit | Verdict | Meaning |
| ---: | --- | --- |
| `0` | `FIX_PROVEN_FOR_THIS_CAPSULE` | Every kill point, including the frozen one, ended exactly once. |
| `1` | `PATCH_FAILED_STILL_REPRODUCES` | The money moved twice. |
| `1` | `PATCH_FAILED_INVARIANT_BROKEN` | The money was lost, tripled, or otherwise wrong. |
| `1` | `BUG_REPRODUCED` | The base reproduced the capsule (`replay --role base`). |
| `2` | `EVIDENCE_INCOMPLETE` | Something could not be observed. Never a fallback, never a guess. |

`nemisis map <tree>` runs the same commit sweep with no verdict: for each store commit, the durable
state a crash there leaves and the state after the retry. It is what an agent reads before it
writes the fix.

## Try to fool it

The checker was red-teamed by hand until it stopped losing, and CI red-teams it on every run.
`nemisis redteam` renders handlers from a grammar over store operations (guard, credit, mark, the
atomic call, the same calls inside `try`/`except` or a retry loop, and the writes around the store
that hostile reviews wrote by hand: a file beside, above, under `~` or `$TMPDIR`, a file tidied
away before returning, a raw SQL write, a table, a pragma, a re-pointed row, a world-detection
attempt; a quarter of them through a helper function), runs `check` on each, and compares the
verdict with an oracle computed from the operation sequence alone. Ten fixed-seed cases run in the
normal suite; a nightly workflow runs three hundred per scenario. Three hand-written handlers that
fooled an earlier engine ship as fixture refs, so the claim is one flag away for anyone:

| Candidate | Unit test | Called twice | Kill + retry | Verdict |
| --- | :-: | :-: | --- | --- |
| `buggy` | green | `$25` | `$50` | `BUG_REPRODUCED` |
| `misleading-green` | green | `$25` | `$50` | `PATCH_FAILED_STILL_REPRODUCES` |
| `mark-first` | green | `$25` | `$0`, marked done | `PATCH_FAILED_INVARIANT_BROKEN` |
| `leftover-credit` | red (`$50` on one call) | `$50` | `$50` | `PATCH_FAILED_STILL_REPRODUCES` |
| `never-marks` | green | `$50` | `$50`, no marker | `PATCH_FAILED_STILL_REPRODUCES` |
| `atomic` | green | `$25` | `$25` | `FIX_PROVEN_FOR_THIS_CAPSULE` |
| `raw-sql` | red (needs SQLite) | n/a | no kill point | `EVIDENCE_INCOMPLETE`, names the one-line change |
| `shadow-table` | red (needs SQLite) | n/a | `$0`, in-flight forever | `EVIDENCE_INCOMPLETE`, the schema changed |
| `tail-bytes` | red (needs SQLite) | n/a | `$25`, then bytes past the file's last page | `EVIDENCE_INCOMPLETE`, a write around the store |

```bash
uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/mark-first
uv run nemisis redteam --cases 100 --seed 1 --out ./redteam   # generate a hundred; there should be no disagreements
```

A handler that writes outside the store still runs; it forfeits the verdict instead of earning one.
`raw-sql` is the textbook fix written as one raw SQL transaction on the store's database: correct,
and unjudgeable, because a write the store did not make has no kill point. CrashCheck names the
write and the store call that expresses the same fix (`store.credit_and_mark(...)`, see [the store
API](PRODUCT.md#the-store-api)) instead of guessing. `shadow-table` keeps its dedup flag in a table
it creates inside the store's own database: an earlier engine blessed it while a crash between that
write and the credit left the customer unpaid forever. `tail-bytes` is the guarded atomic fix
followed by sixteen bytes appended past the database file's last page: the nightly red team caught
the engine issuing verdicts on it for five nights (SQLite's own close had tidied the bytes away
before the engine looked); the engine now reads the file before the worker may exit and pins it
whole during a delivery. Attribution reads the whole database file, the whole world the worker runs
in, and the raw header and length of the file itself, before and after every delivery. Three
hostile reviews found forty-eight handlers an earlier engine blessed; twenty-eight of those shapes
are pinned as refusals. What it cannot read it does not claim; [the boundary](SECURITY.md) lists
the channels that remain.

## Point it at your code

CrashCheck judges one handler shape: a top-level synchronous `def handler(store, event)` with
exactly two positional parameters, no defaults, no `*args`, no `**kwargs`, no alias or re-export.
Every durable write goes through the store CrashCheck injects as the first argument (`CreditStore`:
`processed`, `credit`, `mark_processed`, `credit_and_mark`; `InventoryStore`: `reserved`, `reserve`,
`mark_reserved`, `reserve_and_mark`; [the store API](PRODUCT.md#the-store-api)), against the
scenario's schema, on the scenario's event. Your own connection, your own tables, your own payload
are outside it. `init` reads the signature and nothing more, so `apply_credit(conn, event)` that
runs SQL on `conn` mints a contract and then ends at `EVIDENCE_INCOMPLETE`, exit `2`. Porting a
handler means rewriting its storage calls as store calls, and what survives is the part with the
crash window in it. For an AI agent that is a five-minute subtask; inside that shape, the handler
body is anything you like.

The contract pins the base tree digest, so the fix lives on a branch while the base branch stays at
the tree the contract was accepted for. Committing the contract is safe; `.nemisis/` is outside the
digest.

```bash
nemisis init --issue issue.md --target app.credits:apply_credit --base main
nemisis init --issue issue.md --target app.credits:apply_credit --base main \
  --accept-contract PASTE_PRINTED_DIGEST
git checkout -b fix-double-credit   # the fix is committed here, not on main
nemisis check --base main --candidate HEAD --scenario .nemisis/config.json
```

Commit the accepted `.nemisis/config.json` on the base branch, then copy
[the example workflow](../.github/examples/crashcheck.yml) into `.github/workflows/` to run it on
every pull request:

```bash
curl -o .github/workflows/crashcheck.yml \
  https://raw.githubusercontent.com/Alex-lop/Nemisis/main/.github/examples/crashcheck.yml
```

Every wall-clock wait in the kernel is one budget, ten seconds re-armed for each phase of each
world; its expiry is an `EVIDENCE_INCOMPLETE` naming the phase. `NEMISIS_WORKER_TIMEOUT_SECONDS=30`
raises it on a slow machine; no receipt depends on the value, and a value outside 1 to 600 is
refused rather than clamped.

## Let Nemotron write the patch

NVIDIA's Nemotron on Nebius Token Factory plays the coding agent: it gets the bug report, the buggy
module, and the store API, and nothing about how CrashCheck kills or judges. Its module is accepted
only after deterministic checks (signature, imports, no private attributes), becomes an ordinary
candidate tree, and is judged like any other.

```bash
export NEBIUS_API_KEY=...   # without it: exit 2, nothing written
uv run nemisis propose-patch --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --base fixture:sqlite-credit-v1/buggy --out ./nemotron-candidate
uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate ./nemotron-candidate
```

The report gains a **Candidate author** card with the model's receipt, labelled `LIVE` only for a
real Token Factory call; injected clients are `MOCKED`. This tree has no key, so no `LIVE` receipt
exists yet. See [docs/LIVE_SETUP.md](LIVE_SETUP.md).

## Two scenarios, one kernel

The kernel is written once; a scenario is one object (schema, seed, store, probe, predicate, words).
`sqlite-inventory-v1` is the second: an order reserves two units of a SKU, stock goes 10 to 8, and a
crash between the decrement and its marker oversells to 6.

| Scenario | Effect | Buggy | Agent's rewrite | Atomic | `mark-first` |
| --- | --- | --- | --- | --- | --- |
| `sqlite-credit-v1` | `$0` to `$25` | `$50` | `$50` | `$25` | `$0`, marked done |
| `sqlite-inventory-v1` | 10 to 8 units | 6 units | 6 units | 8 units | 10 units, marked reserved |

Two more scenarios (a Stripe-style webhook idempotency one and a transactional outbox one) are
built and staged; see the open pull requests.

## Verify the project

From a checkout (`git clone … && uv sync --frozen --dev`); an installed tool ships no tests.

```bash
uv run ruff format --check src tests && uv run ruff check src tests
uv run mypy src tests
uv run pytest
```

Every claim in these docs names the test that proves it, and `tests/test_readme_truth.py` fails if
a link, an image, or a test count goes stale:

| Claim | The test that proves it |
| --- | --- |
| A real worker is killed at the durable write, a fresh one replays the same event, five worlds must agree | [`tests/test_sqlite_runner.py`](../tests/test_sqlite_runner.py), [`tests/test_crashcheck.py`](../tests/test_crashcheck.py) |
| A claimed fix is killed once after every store commit it makes (`mark-first` loses the credit) | [`tests/test_verdict_paths.py`](../tests/test_verdict_paths.py) |
| Every durable change is attributed: raw SQL, a shadow table, a pragma, a file, `~`, `TMPDIR` forfeit the verdict | [`tests/test_verdict_paths.py`](../tests/test_verdict_paths.py) |
| Complete-but-wrong is a failed patch, never missing evidence | [`tests/test_crash_models.py`](../tests/test_crash_models.py) |
| The second scenario has its own seed, direction, and predicate and earns the same four verdicts | [`tests/test_inventory_scenario.py`](../tests/test_inventory_scenario.py) |
| Generated handlers agree with an oracle that only knows their operation sequence | [`tests/test_redteam.py`](../tests/test_redteam.py) |
| The README's `init` → accept → `check` sequence runs on a real git repository | [`tests/test_point_at_your_code.py`](../tests/test_point_at_your_code.py) |
| The MCP server's tools carry their truth labels and a blocked model tool writes nothing | [`tests/test_mcp_server.py`](../tests/test_mcp_server.py) |
| `map` is verdict-free and refuses a tree it cannot attribute | [`tests/test_mapping.py`](../tests/test_mapping.py) |
| Truth labels come from code; a config, capsule, or tree cannot claim `LIVE` | [`tests/test_trust_boundaries.py`](../tests/test_trust_boundaries.py) |
| The docs quote the installed engine digest, the reviewed action pin, and the collected test count | [`tests/test_docs_identity.py`](../tests/test_docs_identity.py) |

The original differential verifier (`nemisis verify --fixture idempotency-retry`) is still shipped;
it is where CrashCheck's crash-retry row comes back `UNRESOLVED` and CrashCheck begins.
