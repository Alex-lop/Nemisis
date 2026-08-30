# Demo

## Local hero (about 30 seconds)

```bash
uv sync --dev
uv run nemisis verify --fixture idempotency-retry --mode local
```

Show the `LOCAL FIXTURE` badge, then the matrix:

1. Existing tests pass in both worlds.
2. Ordinary retry changes from assertion failure to pass.
3. Crash-then-retry remains an assertion failure in the candidate.
4. The exact candidate artifact is rejected and the report paths are printed.

Open the emitted `report.html` to show bundle, patch, tree, and receipt bindings.

## Live hero

After configuring the prerequisites in the README:

```bash
uv run nemisis verify --fixture idempotency-retry --mode live
```

The same story should be shown with a `LIVE TOKEN FACTORY` badge, the exact Nemotron model,
ConTree image UUIDs, operation IDs, JUnit hashes, and the byte-identical bundle receipt. This
environment currently lacks credentials/profile/root-image configuration, so no live receipt or
video is claimed.

## Sub-three-minute shot list

1. Read the ticket and show the plausible candidate patch.
2. Run live verification and briefly identify Nemotron claim generation.
3. Hold on the matrix: visible tests green, ordinary retry fixed, crash retry unresolved.
4. Open evidence for exact model, bundle, image, operation, tree, and patch identifiers.
5. End on the rejected artifact and product tagline.
