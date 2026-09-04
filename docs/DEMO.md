# Demo

The timed three-minute version with fallbacks is [DEMO_SCRIPT.md](DEMO_SCRIPT.md); the plain-language
framing is [PITCH.md](PITCH.md). This file is the reference walkthrough.

## 0. Nemotron contract proposal (needs `NEBIUS_API_KEY`)

```bash
uv run nemisis init --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --target app.credits:apply_credit --base fixture:sqlite-credit-v1/buggy \
  --scenario sqlite-credit-v1 --nemotron
```

Show the `nemotron:` line (model, endpoint region, `LIVE`, latency, receipt digest) and the
`proposed:` line (fault intent selected, `amount_cents=2500` matches the audited event). Then pass
`--scenario .nemisis/config.json` to the `check` below so the receipt appears in its report. Without
the key the command exits `2` and drafts nothing; say so and continue with the audited fixture
contract. Never show a `MOCKED` receipt as live.

## 1. Differential foundation

```bash
uv sync --frozen --dev
uv run nemisis verify --fixture idempotency-retry --mode local
```

Show the `LOCAL FIXTURE` label and matrix. The candidate supports ordinary duplicate retry but leaves
the crash-then-retry change witness unresolved. Open the printed report to show that base and
candidate executions share one verification-bundle digest.

This is the original Nemisis thesis: a model or patch cannot authorize itself; observed typed
relations determine the artifact decision.

## 2. CrashCheck counterexample

```bash
uv run nemisis check \
  --base fixture:sqlite-credit-v1/buggy \
  --candidate fixture:sqlite-credit-v1/misleading-green \
  --corrected fixture:sqlite-credit-v1/atomic \
  --mode local
```

Exit `1` and `PATCH_FAILED_STILL_REPRODUCES` are expected. The run should expose this observed
sequence:

1. Exact fixture source identities and tree digests are bound.
2. Exactly two candidate-blind base hypotheses run: `effect-commit-v1` reproduces, while
   `marker-commit-v1` reaches exactly-once state. Their full attempt receipts remain visible.
3. Deterministic selection chooses `effect-commit`. CrashCheck deletes that sole fault action in
   two fresh base worlds; both empty-schedule replays are `EXACTLY_ONCE`, so deletion is rejected
   and the one-action schedule is necessity-proven for this fixture. Hunt outcomes remain in
   `hunt.json`; only the stable deletion decision enters the capsule trace.
4. In each confirmation, `evt_1042` reaches a durable `+$25` effect, the controller sends
   process-group `SIGKILL` and confirms exit `-9`, and a new worker nonce/session replays the
   byte-identical event.
5. Five fresh confirmations per role show the misleading-green candidate at `$50` and the atomic
   control at `$25`, one ledger row,
   and one marker under the same capsule semantics.

The two hunt worlds, two deletion-confirmation worlds, and five fresh worlds per supplied role are
all distinct. CrashCheck receipts cover only hunt, necessity, and kill/restart/replay evidence. The
benchmark—not CrashCheck—runs the fixture's ordinary Pytest suite and sequential duplicate check as
measured context:

```bash
uv run nemisis benchmark --output .nemisis/benchmark.json
```

Present those ordinary green checks as benchmark measurements, never as CrashCheck receipts.

The CLI transport label is `LOCAL`; the manifest/report identifies the audited capsule as
`FIXTURE`. Open the printed `manifest.json` and `report.html` for both hunt receipts, the selected
boundary and one-action deletion trace, five confirmations per role, source bindings,
capsule/event/environment/engine digests, database IDs, worker receipts, nonces, probes, kills, and
final snapshots. Artifact references are relative to the selected output root.

Replay the positive control:

```bash
CAPSULE_PATH=.nemisis/repros/double-credit/PASTE_PRINTED_DIGEST/capsule.json
uv run nemisis replay "$CAPSULE_PATH" \
  --source fixture:sqlite-credit-v1/atomic --role corrected --mode local
```

That replay must exit `0` with `FIX_PROVEN_FOR_THIS_CAPSULE`. The generated regression asset expresses
the same scoped requirement and depends on the installed Nemisis package.

## 3. One-minute evidence viewer

```bash
uv run python -m http.server 8000 --bind 127.0.0.1
```

Open <http://127.0.0.1:8000/docs/assets/crashcheck-hero/> and click **Replay fixture evidence**.
Lead with the verdict and five beats, then expand the exact SHA/tree/capsule/event bindings. This
button reveals committed `LOCAL` / `FIXTURE` evidence only; it does not execute code or contact
Token Factory. A failed benchmark/manifest binding hides the story instead of retaining claims.

## Sub-three-minute CrashCheck sequence

1. Show the benchmark's green Pytest and sequential checks as context.
2. Show both base-only hunt receipts and deterministic `effect-commit` selection.
3. Hold on `timeline: $25.00 durable -> SIGKILL -> fresh worker -> $50.00`.
4. Show five candidate reproductions at `$50` and `PATCH_FAILED_STILL_REPRODUCES`.
5. Replay the unchanged capsule against atomic and show five fresh `$25` confirmations with one
   marker; finish on the scoped—not global—verdict and engine digest.

## Live demonstration

The only implemented provider path is the fixture-limited differential verifier; it has no
current-tree live receipt:

```bash
uv run nemisis doctor --mode live
uv run nemisis verify --fixture idempotency-retry --mode live
```

The current environment may also lack the Token Factory key, usable ConTree profile, or immutable
root image, but CrashCheck has an unconditional additional blocker: its live provider transport is
not implemented. `doctor --mode live` must therefore remain `BLOCKED` even when external
prerequisites are present. Do not substitute local output, mock receipts, provider-looking
identifiers, or a `LIVE` badge. A future live recording must name the exact source SHA and engine
digest, official Nebius endpoint/model, ConTree image and operation identities, and the
guest-produced JUnit trust limitation.
