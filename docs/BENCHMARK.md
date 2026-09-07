# CrashCheck benchmark

Status: measured `LOCAL` / `FIXTURE` evidence generated on 2026-09-06 from clean source commit
`c339aa90f32ec0874b03d51ff8432505596694b2`. The result is
[`benchmarks/results/crashcheck-v1.json`](../benchmarks/results/crashcheck-v1.json).

This benchmark compares ordinary green checks with the real process-kill counterexample for one of
the two audited scenarios, `sqlite-credit-v1`. The other, `sqlite-inventory-v1`, is audited and
checkable but is not benchmarked here. This is not a cloud-performance, arbitrary-repository, or
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
| `buggy` | PASS (1/1, 273.019 ms) | PASS / exactly once (1.600 ms) | `DUPLICATE_EFFECT` | 5/5 | 363.529 ms |
| `misleading-green` | PASS (1/1, 242.885 ms) | PASS / exactly once (0.624 ms) | `DUPLICATE_EFFECT` | 5/5 | 364.912 ms |
| `atomic` | PASS (1/1, 276.303 ms) | PASS / exactly once (0.555 ms) | `EXACTLY_ONCE` | 5/5 | 445.867 ms |

The `buggy` and `misleading-green` outcomes are identical by design, and only their timings differ.
Both trees carry the same check-then-act guard (`if processed: return`, credit, mark) written two
ways, so every ordinary check passes on both and only the crash separates them from `atomic`, which
commits the credit and the marker together. The misleading-green candidate therefore receives
`PATCH_FAILED_STILL_REPRODUCES`: every crash world ends at `$50`, two ledger effects, and one
marker. Every corrected world ends at `$25`, one effect, and one marker.

The hypothesis hunt produced one reproducer from two valid worlds and selected
`effect-commit-v1` by fixed catalog rank. The no-crash control then delivered the event twice with
no kill in 2/2 fresh base worlds and observed `EXACTLY_ONCE` both times, so the base's duplicate is
attributed to the crash. (The JSON still names this the deletion trial.)

Measured local timing:

- time to first base witness: 394.860 ms;
- two-world no-crash control: 345.179 ms;
- complete CrashCheck portion (including the corrected tree's commit sweep): 2.651 s; and
- total benchmark: 3.493 s, taken on 2026-09-07 while a mutation sweep and two other test suites ran on the same laptop.

Timing is diagnostic only. It came from CPython 3.12.13, SQLite 3.53.1, Pytest 9.1.1, Darwin/arm64;
host load can change it. No provider latency, concurrency limit, or cost was measured.

## Exact bindings

- source commit: `c339aa90f32ec0874b03d51ff8432505596694b2`
- engine code digest: `29205c5be25169f0ec17faccddd824e2b931ef0efbcaadae23b6f38c7217e94d`
- capsule digest: `190d62ea98c2884eaeb6f8f30f38bdf0c733e40d186b8cfab8896a691696c0f6`
- event digest: `4ad9ce16a3a060a5dbde7dffafdd7fd2f047e612c4e34c6ca30635355778b293`
- result digest: `7d0672e42f30a30ee7a8cba2c52970e7fffbc9e154ea70b8aad21e26604d5540`

The evidence commit necessarily follows the clean measured source commit. The JSON retains that
immediately preceding SHA rather than pretending the unexecuted evidence commit measured itself.

The capsule and result digests are bound to the measured environment (CPython 3.12.13, SQLite
3.53.1, Darwin arm64) through the runner environment digest. The source commit, the engine code
digest, and the event digest do not depend on the environment. A rerun on another interpreter
prints different capsule and result digests for the same observed behavior.

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
`docs/STATUS.md` and `docs/PROOF.md`, all in one follow-up commit. `tests/test_static_hero.py`
fails until the viewer's `run_id`, the run manifest, and the benchmark JSON agree, and until
`docs/STATUS.md` names the recorded engine digest and commit. No test reads this file, so check the
digests above against the JSON by hand.
