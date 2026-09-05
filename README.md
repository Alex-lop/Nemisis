# Nemisis

**CrashCheck proves an AI patch survives a real crash, not just that its tests pass.**

[![CI](https://github.com/Alex-lop/Nemisis/actions/workflows/ci.yml/badge.svg)](https://github.com/Alex-lop/Nemisis/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB.svg)

A coding agent fixes "retries sometimes credit an order twice". Its patch passes the test suite.
It passes an ordinary call-it-twice check. Then a worker is `SIGKILL`ed right after the `$25`
credit hits disk, the retry runs in a fresh process, and the account holds `$50`.

```text
$ uv run nemisis check --base fixture:sqlite-credit-v1/buggy \
    --candidate fixture:sqlite-credit-v1/misleading-green --corrected fixture:sqlite-credit-v1/atomic

verdict: PATCH_FAILED_STILL_REPRODUCES
timeline: $25.00 durable -> SIGKILL -> fresh worker -> $50.00
```

![Thirty-second terminal recording: the buggy handler reproduces the double credit, the agent's green patch still reproduces it under the same kill and retry, and the atomic fix ends at exactly one credit](docs/assets/screenshots/crashcheck-demo.gif)

Exit `1` blocks the merge. The same frozen crash replayed against the real fix exits `0`.

## Try it

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), and a POSIX machine (macOS or Linux).

```bash
git clone https://github.com/Alex-lop/Nemisis.git && cd Nemisis
uv sync --frozen --dev
uv run nemisis check --base fixture:sqlite-credit-v1/buggy \
  --candidate fixture:sqlite-credit-v1/misleading-green \
  --corrected fixture:sqlite-credit-v1/atomic
```

About two seconds. Then replay the frozen crash against the fix (the `capsule:` path is printed
by `check`):

```bash
uv run nemisis replay .nemisis/repros/double-credit/*/capsule.json \
  --source fixture:sqlite-credit-v1/atomic --role corrected
```

## What it does

CrashCheck runs the exact patch in a real worker process and treats every durable write as a place
the process could die.

1. **Hunt on the base.** Two fixed kill points are tried on the buggy tree before the candidate is
   even read; the one that reproduces the duplicate is frozen into a content-addressed capsule.
2. **No-crash control.** The base is delivered the same event twice with no kill. It ends exactly
   once, so the duplicate needs the crash: this is a crash/retry bug, not a broken handler.
3. **Kill, restart, replay.** Five fresh worlds per tree. Each one seeds a database, waits until the
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

## Try to fool it

The checker was red-teamed against thirty adversarially written handlers. Three that fooled an
earlier engine ship as fixture refs, so the claim above is one flag away for anyone:

| Candidate | Unit test | Called twice | Kill + retry | Verdict |
| --- | :-: | :-: | --- | --- |
| `buggy` | green | `$25` | `$50` | `BUG_REPRODUCED` |
| `misleading-green` | green | `$25` | `$50` | `PATCH_FAILED_STILL_REPRODUCES` |
| `mark-first` | green | `$25` | `$0`, marked done | `PATCH_FAILED_INVARIANT_BROKEN` |
| `leftover-credit` | green | `$50` | `$50` | `PATCH_FAILED_STILL_REPRODUCES` |
| `never-marks` | green | `$50` | `$50`, no marker | `PATCH_FAILED_STILL_REPRODUCES` |
| `atomic` | green | `$25` | `$25` | `FIX_PROVEN_FOR_THIS_CAPSULE` |

```bash
uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/mark-first
```

Or write your own in thirty seconds:

```bash
uv run nemisis export fixture:sqlite-credit-v1/buggy ./my-candidate
$EDITOR ./my-candidate/app/credits.py
uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate ./my-candidate
```

The handler may only touch the store; a write around it is an integrity failure, not a verdict.

## Let Nemotron write the patch

The hackathon story, made literal. NVIDIA's Nemotron on Nebius Token Factory plays the coding
agent: it gets the bug report, the buggy module, and the store API, and nothing about how
CrashCheck kills or judges. Its module is accepted only after deterministic checks (signature,
imports, no private attributes), becomes an ordinary candidate tree, and is judged like any other.

```bash
export NEBIUS_API_KEY=...   # without it: exit 2, nothing written
uv run nemisis propose-patch --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --base fixture:sqlite-credit-v1/buggy --out ./nemotron-candidate
uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate ./nemotron-candidate
```

The report gains a **Candidate author** card with the model's receipt. It is labelled `LIVE` only
for a real Token Factory call; injected clients are `MOCKED` and say so. This tree has no key, so no
`LIVE` receipt exists yet. `init --nemotron` is the second, smaller model job: proposing the
contract's catalog binding, candidate-blind. See [docs/LIVE_SETUP.md](docs/LIVE_SETUP.md).

## Point it at your code

The alpha audits one handler shape: a synchronous `module:function(store, event)` that uses the
`CreditStore` API (`processed`, `credit`, `mark_processed`, `credit_and_mark`) against SQLite. Inside
that shape, the handler body is anything you like.

```bash
uv tool install "git+https://github.com/Alex-lop/Nemisis@main"
nemisis init --issue issue.md --target app.credits:apply_credit --base main
nemisis init --issue issue.md --target app.credits:apply_credit --base main \
  --accept-contract PASTE_PRINTED_DIGEST
nemisis check --base main --candidate HEAD --scenario .nemisis/config.json
```

Commit the accepted `.nemisis/config.json` on the base branch, then drop
[the example workflow](.github/examples/crashcheck.yml) into `.github/workflows/` to run it on every
pull request. Adding a second scenario (another schema, store, and predicate) is the next seam; the
kill/restart/replay kernel is not tied to credits, but today's catalog is.

## What it never does

- Never pushes, merges, comments, or touches your git history. It writes `.nemisis/` and exits.
- Never upgrades a label. Local runs are `LOCAL`, the packaged case is `FIXTURE`, injected model
  clients are `MOCKED`, `LIVE` needs a genuine provider receipt. Missing evidence fails closed.
- Never lets a model near the verdict. Models write patches or propose catalog IDs; deterministic
  code owns probes, kill points, and decisions.
- Not a sandbox. Local mode is for a trusted checkout; the GitHub Action refuses fork PRs until
  the kernel runs inside a Token Factory Sandbox. Kill points are store commits, so durable state a
  handler keeps outside the store (a dedup file, another database) has windows CrashCheck cannot
  reach, and says so.

## Verify the project

```bash
uv run ruff format --check src tests && uv run ruff check src tests
uv run mypy src tests
uv run pytest
```

Every claim above has a test behind it; `tests/test_readme_truth.py` fails if a link or image here
goes stale. The terminal captures are regenerated by the `vhs` tapes in
[docs/assets/screenshots/](docs/assets/screenshots/).

## Docs

[Product contract](docs/PRODUCT.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Security boundary](docs/SECURITY.md) · [Proof ledger](docs/PROOF.md) ·
[Benchmark](docs/BENCHMARK.md) · [90-second demo](docs/DEMO.md) · [Pitch](docs/PITCH.md) ·
[Live setup](docs/LIVE_SETUP.md) · [Status](docs/STATUS.md) · [Decisions](docs/DECISIONS.md)

The original differential verifier (`nemisis verify --fixture idempotency-retry`) is still shipped;
it is where CrashCheck's crash-retry row comes back `UNRESOLVED` and CrashCheck begins.

Apache-2.0. See [LICENSE](LICENSE).
