# Nemisis

> Don't ask whether the coding agent says it is done. Make the exact patch prove each claim.

The spelling **Nemisis** is intentional. One breath: AI coding agents ship retry patches that look
green and still double-charge in production; CrashCheck kills the worker after the money moves,
restarts it, replays the same event, and checks the database for a duplicate. See the
[one-page pitch](docs/PITCH.md) and the [timed demo script](docs/DEMO_SCRIPT.md).

Nemisis CrashCheck turns a green-looking retry-safety patch into an executed counterexample: it
kills a real worker after a durable side effect, starts a fresh worker, replays the identical event,
and determines whether the exact patch stopped the duplicate effect. The verdict comes from durable
state and process receipts—not model confidence.

CrashCheck is the narrow crash/retry product built on Nemisis's broader deterministic differential
verification foundation. Both surfaces remain available; neither claims universal patch safety.

## CrashCheck quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen --dev
uv run nemisis check \
  --base fixture:sqlite-credit-v1/buggy \
  --candidate fixture:sqlite-credit-v1/misleading-green \
  --corrected fixture:sqlite-credit-v1/atomic \
  --mode local
```

The packaged SQLite case applies event `evt_1042`, which should grant one `$25` credit. The
misleading-green revision passes its small existing suite and an ordinary sequential duplicate
check, yet still reaches `$50` after a real `SIGKILL` and retry. The atomic revision ends at `$25`,
one ledger effect, and one processed marker under the same capsule. The measured comparison is
published by `uv run nemisis benchmark`; CrashCheck receipts themselves remain limited to the
kill/restart/replay evidence.

`PATCH_FAILED_STILL_REPRODUCES` and exit `1` are the expected result. Before reading the candidate,
the run executes two fixed base-only hypotheses in parallel and selects the reproducing
`effect-commit` boundary. CrashCheck deletes that sole fault action and runs the empty schedule in
two fresh base worlds; both end exactly once, so deletion is rejected and this one-action schedule
is necessary for the fixture witness. This is not a general minimizer. It then records five fresh
proof worlds per supplied tree, exact source bindings, durable probes, confirmed worker exits, new
worker nonces, and final snapshots.
CrashCheck does not run the fixture's ordinary repository tests; the benchmark measures those
separately as context for the counterexample.

Replay the atomic revision using the exact `capsule:` path printed by `check`:

```bash
CAPSULE_PATH=.nemisis/repros/double-credit/PASTE_PRINTED_DIGEST/capsule.json
uv run nemisis replay "$CAPSULE_PATH" \
  --source fixture:sqlite-credit-v1/atomic --role corrected --mode local
```

CrashCheck uses `LOCAL` as the execution transport. The packaged audited contract and capsule carry
the separate `FIXTURE` truth label in the manifest and report. Neither label means `LIVE`.

### Draft the contract with Nemotron

`init --nemotron` asks `nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory to read the
issue and the exact base handler, select audited catalog IDs, and propose the expected single
effect. It never sees a candidate. Deterministic code accepts the proposal only when it names the
audited fault intent and the exact `amount_cents`; otherwise nothing is drafted and the command
exits `2` with the model's actual values. The sanitized receipt lands in `.nemisis/proposal.json`,
and `check --scenario .nemisis/config.json` carries it into the manifest and report as provenance.
It is labelled `LIVE` only for a genuine Token Factory call, it is never crash evidence, and it never
touches the verdict.

```bash
export NEBIUS_API_KEY=...   # Token Factory key; without it the command fails closed
uv run nemisis init --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --target app.credits:apply_credit --base fixture:sqlite-credit-v1/buggy \
  --scenario sqlite-credit-v1 --nemotron
uv run nemisis check --base fixture:sqlite-credit-v1/buggy \
  --candidate fixture:sqlite-credit-v1/misleading-green \
  --corrected fixture:sqlite-credit-v1/atomic \
  --scenario .nemisis/config.json --mode local
```

The model call is bounded to structured output over the audited catalog; the prompt template, input,
and response are recorded by digest only. No key, issue text, handler source, or raw response enters
the receipt.

### Open the one-minute evidence viewer

From the repository root, serve the committed static evidence:

```bash
uv run python -m http.server 8000
```

Open <http://127.0.0.1:8000/docs/assets/crashcheck-hero/> and select **Replay fixture evidence**.
The control reveals the committed, digest-bound `LOCAL` / `FIXTURE` receipt; it does not execute
repository code, call a model, or start a provider run. If either JSON binding fails, the viewer
shows no behavioral claim.

### Use the audited SQLite adapter in a trusted repository

`init` writes strict JSON at `.nemisis/config.json`. A non-packaged contract remains `DRAFT` until
the exact printed digest is accepted. This alpha does not analyze arbitrary handlers, databases, or
languages; it accepts only `sqlite-credit-v1` and the fixed two-argument `CreditStore` contract.

```bash
uv run nemisis init --issue issue.md --target app.credits:apply_credit --base main \
  --scenario sqlite-credit-v1
uv run nemisis init --issue issue.md --target app.credits:apply_credit --base main \
  --scenario sqlite-credit-v1 --accept-contract PASTE_PRINTED_DIGEST
uv run nemisis check --base main --candidate HEAD \
  --scenario .nemisis/config.json --mode local
```

Passing the reviewed config explicitly supports this pre-commit first run. Once the config is
committed on the base ref, the scenario ID loads only that exact base-owned copy; cwd and candidate
copies cannot override it.

Git refs are resolved to full commit SHAs. Fixture refs retain their exact fixture identity; local
directories are identified by their copied tree digest. Each `AnchorBinding` records the supplied
ref, resolved identity, and tree digest. `.git`, `.nemisis`, bytecode, and local pytest/mypy caches
are excluded from source materialization and cannot perturb the bound source tree.

CrashCheck commands support `--json`; progress stays on stderr. Their exit policy is:

| Exit | Meaning |
| ---: | --- |
| `0` | `FIX_PROVEN_FOR_THIS_CAPSULE` |
| `1` | `BUG_REPRODUCED` or `PATCH_FAILED_STILL_REPRODUCES` |
| `2` | `EVIDENCE_INCOMPLETE`, `UNSUPPORTED_TARGET`, invalid input, or infrastructure failure |

Every run writes a manifest beneath `.nemisis/runs/<run-id>/`. Attempt-bearing runs add a report;
the golden path also records the full single-action deletion receipt. A pre-execution mapping
failure instead adds `anchor-resolution.json`. Immutable repro assets live under
`.nemisis/repros/double-credit/<capsule-digest>/`; completed runs add the executable integration/fault
regression. Stored paths are artifact-root-relative, so the bundle can move without retaining a
host path.

## Differential verifier

The original verifier remains available:

```bash
uv run nemisis verify --fixture idempotency-retry --mode local
```

It runs real subprocesses in separate temporary base and candidate worlds. The same trusted
baseline tests, adversarial tests, runner definition, parser, and bundle bytes run in both worlds.

| Claim | Relation | Base | Candidate | Verdict |
| --- | --- | --- | --- | --- |
| Reserve available inventory | `INVARIANT` | `PASS` | `PASS` | `SUPPORTED` |
| Reject out-of-stock inventory | `INVARIANT` | `PASS` | `PASS` | `SUPPORTED` |
| Ordinary duplicate retry | `CHANGE_WITNESS` | `ASSERTION_FAIL` | `PASS` | `SUPPORTED` |
| Crash then retry | `CHANGE_WITNESS` | `ASSERTION_FAIL` | `ASSERTION_FAIL` | `UNRESOLVED` |

`LOCAL FIXTURE` means observed local execution of checked-in inputs, not Token Factory evidence.

## GitHub pull requests

Copy [the hardened example](.github/examples/crashcheck.yml) to
`.github/workflows/crashcheck.yml` and commit the accepted base-owned configuration. The example
pins Nemisis to a reviewed full commit SHA and uses `pull_request`, read-only contents permission,
credential-free checkout, a bounded job, a new runner-temporary artifact directory, a job summary,
and uploaded evidence. It refuses untrusted forks because local mode is not a hostile-code sandbox;
those candidates remain blocked until CrashCheck's ConTree transport exists.

## Live boundaries

The original differential verifier has a fixture-only live path:

```bash
uv run nemisis verify --fixture idempotency-retry --mode live
```

It requires `NEBIUS_API_KEY`, a valid ConTree profile, and an immutable UUID in
`NEMISIS_CONTREE_ROOT_IMAGE`. Token Factory defaults to the official global endpoint
`https://api.tokenfactory.nebius.com/v1/` and model
`nvidia/nemotron-3-super-120b-a12b`; an override must still be an official Nebius global or regional
HTTPS `/v1` endpoint. ConTree is constructed from the official client profile.

This live verifier is intentionally limited to the audited `idempotency-retry` fixture and its
validated generated-test subset. Its JUnit report is guest-produced evidence returned through
bounded Sandbox output, not a provider-owned test attestation; arbitrary repositories are not
supported by that trust channel. Networking is disabled during execution.

CrashCheck's own live call is `init --nemotron`; it needs only `NEBIUS_API_KEY`. CrashCheck's
`--mode live` provider transport (running the kill/replay kernel inside a Token Factory Sandbox) is
not yet connected and fails closed. The current environment lacks the Token Factory key, a usable
ConTree profile, and an immutable root image, so there is no current-tree `LIVE` or `RECORDED_LIVE`
receipt for either surface. Nothing falls back to local mode. Run `uv run nemisis doctor --mode live`
for the independent prerequisite checks.

## Verify the project

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src tests
uv run pytest
uv build
```

See [product scope](docs/PRODUCT.md), [architecture](docs/ARCHITECTURE.md),
[security boundary](docs/SECURITY.md), [proof ledger](docs/PROOF.md), and the
[benchmark protocol](docs/BENCHMARK.md). The [live runbook](docs/LIVE_RUNBOOK.md) records exact
provider prerequisites and current blockers without substituting local evidence.

Licensed under Apache-2.0; see [LICENSE](LICENSE).
