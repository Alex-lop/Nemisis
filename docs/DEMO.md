# Demo

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
3. Deterministic selection chooses `effect-commit`; the capsule's minimization trace records both
   tried semantic hypotheses without candidate input or volatile host identity.
4. In each confirmation, `evt_1042` reaches a durable `+$25` effect, the controller sends
   process-group `SIGKILL` and confirms exit `-9`, and a new worker nonce/session replays the
   byte-identical event.
5. Five fresh confirmations per role show the misleading-green candidate at `$50` and the atomic
   control at `$25`, one ledger row,
   and one marker under the same capsule semantics.

The two hunt worlds are separate from the five fresh worlds per supplied role. CrashCheck receipts
cover only hunt and kill/restart/replay evidence. The benchmark—not CrashCheck—runs the fixture's
ordinary Pytest suite and sequential duplicate check as measured context:

```bash
uv run nemisis benchmark --output .nemisis/benchmark.json
```

Present those ordinary green checks as benchmark measurements, never as CrashCheck receipts.

The CLI transport label is `LOCAL`; the manifest/report identifies the audited capsule as
`FIXTURE`. Open the printed `manifest.json` and `report.html` for both hunt receipts, the selected
boundary and minimization trace, five confirmations per role, source bindings,
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

## Sub-three-minute CrashCheck sequence

1. Show the benchmark's green Pytest and sequential checks as context.
2. Show both base-only hunt receipts and deterministic `effect-commit` selection.
3. Hold on `+$25 durable -> SIGKILL -> fresh worker` in the confirmation trace.
4. Show five candidate reproductions at `$50` and `PATCH_FAILED_STILL_REPRODUCES`.
5. Replay the unchanged capsule against atomic and show five fresh `$25` confirmations with one
   marker; finish on the scoped—not global—verdict and engine digest.

## Live demonstration

The only integrated live execution is the fixture-limited differential verifier:

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
