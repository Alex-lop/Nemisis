# CrashCheck benchmark

Status: measured `LOCAL` / `FIXTURE` evidence generated on 2026-09-06 from clean source commit
`14cd428bc01d4da44bf05758afb1cb69188479f5`. The result is
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
| `buggy` | PASS (1/1, 140.953 ms) | PASS / exactly once (1.443 ms) | `DUPLICATE_EFFECT` | 5/5 | 338.785 ms |
| `misleading-green` | PASS (1/1, 106.646 ms) | PASS / exactly once (0.670 ms) | `DUPLICATE_EFFECT` | 5/5 | 322.594 ms |
| `atomic` | PASS (1/1, 104.579 ms) | PASS / exactly once (0.791 ms) | `EXACTLY_ONCE` | 5/5 | 325.144 ms |

The `buggy` and `misleading-green` rows are identical by design: both trees carry the same
check-then-act guard (`if processed: return`, credit, mark) written two ways, so every ordinary check
passes on both and only the crash separates them from `atomic`, which commits the credit and the
marker together. The misleading-green candidate therefore receives `PATCH_FAILED_STILL_REPRODUCES`:
every crash world ends at `$50`, two ledger effects, and one marker. Every corrected world ends at
`$25`, one effect, and one marker.

The hypothesis hunt produced one reproducer from two valid worlds and selected
`effect-commit-v1` by fixed catalog rank. The no-crash control then delivered the event twice with
no kill in 2/2 fresh base worlds and observed `EXACTLY_ONCE` both times, so the base's duplicate is
attributed to the crash. (The JSON still names this the deletion trial.)

Measured local timing:

- time to first base witness: 269.272 ms;
- two-world no-crash control: 271.980 ms;
- complete CrashCheck portion (including the corrected tree's commit sweep): 2.108 s; and
- total benchmark: 2.517 s.163 s.

Timing is diagnostic only. It came from CPython 3.12.13, SQLite 3.53.1, Pytest 9.1.1, Darwin/arm64;
host load can change it. No provider latency, concurrency limit, or cost was measured.

## Exact bindings

- source commit: `14cd428bc01d4da44bf05758afb1cb69188479f5`
- engine code digest: `39833a5640c9053727c7832d6b72ddb14b4684d21b04daa6043c4e32c182e53b`
- capsule digest: `800b4651c63b4f4a091d6366d84bcea65931f52da872e3068fd1bc4ef7db4572`
- event digest: `4ad9ce16a3a060a5dbde7dffafdd7fd2f047e612c4e34c6ca30635355778b293`
- result digest: `b7a03b92f4bb8cf1a6416b1e88a4ff26d62f74d5fd172607d800c8aab7b96643`

The evidence commit necessarily follows the clean measured source commit. The JSON retains that
immediately preceding SHA rather than pretending the unexecuted evidence commit measured itself.

The capsule and result digests are bound to the measured environment (CPython 3.12.13, SQLite
3.53.1, Darwin arm64) through the runner environment digest; only the engine code digest is
environment-independent. A rerun on another interpreter prints different capsule and result
digests for the same observed behavior.

Regenerate with:

```bash
uv run nemisis benchmark --output benchmarks/results/crashcheck-v1.json --json
```

The command refuses a dirty execution-critical tree, validates the complete result against its
strict schema and digests, and replaces the output file. Wall-clock timings enter `result_digest`,
so every run publishes a new result digest even for identical behavior. The committed viewer binds
this file to a manifest, so regenerating it is a set: rerun `check` with
`--output-dir docs/assets/crashcheck-hero`, replace the old `runs/<run-id>/` and
`repros/double-credit/<capsule-digest>/` directories with the new ones, point the `run_id` in
`docs/assets/crashcheck-hero/index.html` at the new run, and update the digests above and in
`docs/STATUS.md` and `docs/PROOF.md`, all in one follow-up commit; `tests/test_static_hero.py`
fails until the set is consistent.
