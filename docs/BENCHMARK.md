# Benchmark

Status: protocol and deterministic JSON schema implemented. The committed measurement is generated
only after the final execution-critical SHA is frozen.

The benchmark will reuse the one audited `sqlite-credit-v1` fixture; it will not create a parallel
scenario framework or duplicate source trees.

## Cases

| Variant | Oracle |
| --- | --- |
| `buggy` | Duplicate durable effect exists |
| `misleading-green` | Ordinary duplicate is handled, crash/retry duplicate still exists |
| `atomic` | One durable effect and one processed marker |

The oracle table defines expected relations; it is not an observed result.

## Compared checks

Each exact tree will be evaluated by:

1. the repository's existing test;
2. the ordinary sequential duplicate check;
3. CrashCheck's real kill, fresh restart, identical-event replay, and frozen capsule.

CrashCheck claims require five independently prepared worlds per tree. Every world must have a
unique run, database, worker nonce, and IPC session while retaining the same capsule and event
digests.

## Recorded metrics

- reproduced bug cases and false reproduction labels;
- attempted hypothesis worlds and time to first witness;
- one-action deletion result, two no-fault confirmations, and retained-action ratio;
- five-run replay stability;
- base/candidate/corrected relation correctness;
- local wall time.

Provider latency and cost will be omitted until genuine current-tree receipts exist. Model
self-review will not be fabricated as a baseline.

## Publication rule

The result records the exact execution-critical source SHA, Python/SQLite/environment identity,
three exact tree digests, per-run outcomes, and raw durations. `README.md` and the demo may quote
only those measured values.

If a results-only documentation commit follows the measurement, it must still name the immediately
prior tested engine SHA rather than implying that an unexecuted later tree was measured.
