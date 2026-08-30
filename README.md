# Nemisis

> Don't ask whether the coding agent says it is done. Make the exact patch prove each claim.

Nemisis is an adversarial differential-verification agent for AI-generated patches.
Nemotron converts a ticket and candidate diff into typed executable claims; Token Factory
Sandboxes run one immutable verification bundle against exact base and candidate snapshots;
deterministic evidence, not model confidence, decides whether the patch survives.

The first fixture is an inventory reservation patch that passes the repository's existing tests
and handles an ordinary duplicate request, but still decrements inventory twice when the first
attempt crashes after its side effect.

## Run the local hero

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --dev
uv run nemisis verify --fixture idempotency-retry --mode local
```

The command performs real subprocess executions in separate temporary filesystem worlds and
writes a JSON manifest plus a static HTML report under `.nemisis/runs/`. Its expected matrix is:

| Claim | Relation | Base | Candidate | Verdict |
| --- | --- | --- | --- | --- |
| Reserve available inventory | `INVARIANT` | `PASS` | `PASS` | `SUPPORTED` |
| Reject out-of-stock inventory | `INVARIANT` | `PASS` | `PASS` | `SUPPORTED` |
| Ordinary duplicate retry | `CHANGE_WITNESS` | `ASSERTION_FAIL` | `PASS` | `SUPPORTED` |
| Crash then retry | `CHANGE_WITNESS` | `ASSERTION_FAIL` | `ASSERTION_FAIL` | `UNRESOLVED` |

`LOCAL FIXTURE` is development evidence, not Token Factory evidence. A rejected candidate still
returns a successful CLI process because Nemisis completed its job; the artifact receipt carries
the acceptance decision.

## Run the live path

Live mode never falls back to local execution. It requires:

- `NEBIUS_API_KEY` for Token Factory inference;
- a configured ConTree profile (`CONTREE_PROFILE` or `~/.config/contree/auth.ini`);
- `NEMISIS_CONTREE_ROOT_IMAGE`, set to an immutable ConTree image UUID containing `/bin/sh`,
  `/bin/tar`, `/usr/bin/env`, `python` and `git` on the fixed system `PATH`, and an importable
  `pytest` package.

Then run:

```bash
uv run nemisis verify --fixture idempotency-retry --mode live
```

The current default is the global Token Factory endpoint and
`nvidia/nemotron-3-super-120b-a12b`. Nemisis validates that exact model and structured-output
capability through the live model catalog before generation. The Sandbox path uploads the source,
validated patch, and one byte-identical bundle; creates persistent common/base/candidate images;
checks exact tree digests; and derives granular outcomes from trusted JUnit annotations.
The packaged duplicate and crash-window claims remain mandatory acceptance gates in every live
bundle; Nemotron-generated claims add adversarial evidence but cannot omit those ticket promises.

That JUnit channel is limited to the audited packaged fixture/candidate and validated generated-test
subset, with Sandbox networking disabled. ConTree client 0.3.0 exposes guest-written files and
stdout, not a provider-owned result stream, so arbitrary repositories are unsupported until such a
channel exists.

See the official [Token Factory quickstart](https://docs.tokenfactory.nebius.com/quickstart) and
[ConTree authentication guide](https://docs.tokenfactory.nebius.com/sandboxes/cli/tutorial/installation).

## Verify the project

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src tests
uv run pytest
uv build
```

The code is intentionally narrow: one fixture, one model, one local backend, one ConTree backend,
and one CLI/HTML evidence surface. Repair automation and a web server remain gated on a genuine
current-tree live run.

Truth labels are not interchangeable: `LIVE`, `RECORDED_LIVE`, `LOCAL`, `FIXTURE`, `MOCKED`,
`PLANNED`, and `BLOCKED` retain their literal meanings in evidence records.

Licensed under Apache-2.0; see [LICENSE](LICENSE).
