# CrashCheck benchmark

Status: measured `LOCAL` / `FIXTURE` evidence generated on 2026-09-05 from clean source commit
`305667621ef62b49523d35a65491dafbf1e779ef`. The result is
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
| `buggy` | PASS (1/1, 113.670 ms) | PASS / exactly once (1.192 ms) | `DUPLICATE_EFFECT` | 5/5 | 271.661 ms |
| `misleading-green` | PASS (1/1, 98.296 ms) | PASS / exactly once (0.576 ms) | `DUPLICATE_EFFECT` | 5/5 | 265.878 ms |
| `atomic` | PASS (1/1, 98.683 ms) | PASS / exactly once (0.545 ms) | `EXACTLY_ONCE` | 5/5 | 256.213 ms |

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

- time to first base witness: 259.309 ms;
- two-world no-crash control: 238.623 ms;
- complete CrashCheck portion (including the corrected tree's commit sweep): 1.809 s; and
- total benchmark: 2.163 s.

Timing is diagnostic only. It came from CPython 3.12.13, SQLite 3.53.1, Pytest 9.1.1, Darwin/arm64;
host load can change it. No provider latency, concurrency limit, or cost was measured.

## Exact bindings

- source commit: `305667621ef62b49523d35a65491dafbf1e779ef`
- engine code digest: `a9b1227d5c32db9500232be0a161906a23128f7c95d5d9e06c82a26bc34897ad`
- capsule digest: `41a29044bceec3314dc82d6261cc4f53e7e28a218759c09deecb97825266d99c`
- event digest: `4ad9ce16a3a060a5dbde7dffafdd7fd2f047e612c4e34c6ca30635355778b293`
- result digest: `fe98afd23f5a5bf3b5cf72a52a42558f2fb6d32ef848392fbc7f6dd26b51f8ef`

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
