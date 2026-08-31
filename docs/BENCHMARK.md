# CrashCheck benchmark

Status: measured `LOCAL` / `FIXTURE` evidence generated from clean source commit
`ddaf186aa81b8a7ebd442da1f2dfeee6878e7dce`. The result is
[`benchmarks/results/crashcheck-v1.json`](../benchmarks/results/crashcheck-v1.json).

This benchmark compares ordinary green checks with the real process-kill counterexample for the
one audited `sqlite-credit-v1` scenario. It is not a cloud-performance, arbitrary-repository, or
general schedule-search benchmark.

## Protocol

For each exact fixture tree, the runner measures:

1. its existing one-test Pytest suite;
2. two ordinary sequential deliveries; and
3. CrashCheck's parent-controlled `SIGKILL`, confirmed worker death, fresh-process identical-event
   replay, and independently probed durable state.

CrashCheck first runs two fixed base-only hypotheses. It then deletes the selected schedule's sole
fault action and requires two fresh no-fault base worlds to finish exactly once. Five additional
fresh confirmation worlds are required for each base, candidate, and corrected role.

## Observed matrix

| Variant | Existing test | Sequential duplicate | CrashCheck | Valid worlds | CrashCheck wall |
| --- | --- | --- | --- | ---: | ---: |
| `buggy` | PASS (1/1, 154.515 ms) | PASS / exactly once (1.341 ms) | `DUPLICATE_EFFECT` | 5/5 | 464.276 ms |
| `misleading-green` | PASS (1/1, 113.530 ms) | PASS / exactly once (0.611 ms) | `DUPLICATE_EFFECT` | 5/5 | 414.171 ms |
| `atomic` | PASS (1/1, 112.197 ms) | PASS / exactly once (0.597 ms) | `EXACTLY_ONCE` | 5/5 | 345.884 ms |

The misleading-green candidate therefore receives `PATCH_FAILED_STILL_REPRODUCES`: every crash
world ends at `$50`, two ledger effects, and one marker. Every corrected world ends at `$25`, one
effect, and one marker.

The hypothesis hunt produced one reproducer from two valid worlds and selected
`effect-commit-v1` by fixed catalog rank. One sole-fault-action deletion trial then observed
`EXACTLY_ONCE` in 2/2 fresh base worlds, rejected deletion, and retained 1/1 fault actions. This is
a fixture-scoped necessity proof, not a general minimizer.

Measured local timing:

- time to first base witness: 294.779 ms;
- two-world deletion proof: 327.369 ms;
- complete CrashCheck portion: 1.935 s; and
- total benchmark: 2.378 s.

Timing is diagnostic only. It came from CPython 3.12.13, SQLite 3.53.1, Pytest 9.1.1, Darwin/arm64;
host load can change it. No provider latency, concurrency limit, or cost was measured.

## Exact bindings

- source commit: `ddaf186aa81b8a7ebd442da1f2dfeee6878e7dce`
- engine code digest: `47d78405ca59dee877328e16face03b15af484e3d65811e8caf213f00d8ec912`
- capsule digest: `1025d9c6e014394cf80629d180e7cb4fb1a77a4b7b26934980b5f5ea975069a8`
- event digest: `4ad9ce16a3a060a5dbde7dffafdd7fd2f047e612c4e34c6ca30635355778b293`
- result digest: `11016ce964b88961c246c91eb1ae437cf0ff9e9547a794ad845776af52af864a`

The evidence commit necessarily follows the clean measured source commit. The JSON retains that
immediately preceding SHA rather than pretending the unexecuted evidence commit measured itself.
Regenerate with:

```bash
uv run nemisis benchmark --output benchmarks/results/crashcheck-v1.json --json
```

The command refuses a dirty execution-critical tree, validates the complete result against its
strict schema and digests, and refuses to overwrite different evidence.
