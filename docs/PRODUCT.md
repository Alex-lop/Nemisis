# Product contract

Nemisis CrashCheck is counterexample CI for stateful Python patches. It gives a backend developer
or reviewer deterministic evidence before trusting a retry/idempotency patch produced by a human or
coding agent.

The alpha answers one scoped question:

> Did this exact Python/SQLite revision defeat this frozen kill/restart/replay capsule while the
> independently observed durable invariants held?

The original `nemisis verify` differential fixture remains available as a secondary foundation.
CrashCheck is the primary product surface.

## Alpha inputs and authority

- Input: issue text, one synchronous `module:function` target, exact base and candidate sources,
  and an optional corrected control.
- Contract: accepted, base-owned JSON selecting only the fixed `sqlite-credit-v1` event, fault,
  probe, predicate, and adapter catalog.
- Output: every run publishes a JSON manifest. Attempt-bearing runs add a static report; completed
  golden-path checks add a content-addressed Repro Capsule and executable regression. A
  pre-execution anchor failure instead adds a structured anchor-resolution receipt.
- Authority: models may propose bounded catalog choices and scalar values. Strict schemas, digests,
  parent-owned execution, read-only probes, and fixed classification rules alone decide the result.

`LOCAL` is an execution transport. `FIXTURE` identifies audited checked-in inputs. `LIVE` requires
genuine current-tree provider receipts. None of these labels is interchangeable.

The repository workflow is one sequence: run `init`, review its draft and printed digest, rerun
`init --accept-contract <digest>`, commit the base-owned `.nemisis/config.json`, then run `check`.
The packaged fixture command is the audited shortcut because its contract is already accepted.

## Five-beat CrashCheck story

1. Bind the accepted issue, target, exact base tree, canonical event, and trusted catalog IDs.
2. Before candidate materialization, run two fixed base hypotheses, select the canonical
   reproducer, then delete its sole fault action in two fresh worlds. Proceed only when both
   no-fault replays finish exactly once, proving this one-action schedule necessary for the
   counterexample.
3. In every proof world, observe the durable `$25` effect, send process-group `SIGKILL`, confirm
   exit `-9`, start a fresh worker, and replay the byte-identical event.
4. Require five fresh base and candidate worlds, plus five corrected worlds when supplied. Fixed
   rules emit the verdict from independently probed durable state.
5. For the complete path, publish capsule, contract, event, hunt, single-action necessity receipt,
   metadata, regression, manifest, and report. `replay` evaluates the unchanged capsule against
   another exact tree.

## Verdict contract

| Verdict | Exit | Exact meaning |
| --- | ---: | --- |
| `BUG_REPRODUCED` | 1 | The exact base reproduced the capsule's duplicate effect. |
| `PATCH_FAILED_STILL_REPRODUCES` | 1 | The exact candidate reproduced the same duplicate effect. |
| `FIX_PROVEN_FOR_THIS_CAPSULE` | 0 | The exact candidate completed exactly once in every required world for this capsule only. |
| `EVIDENCE_INCOMPLETE` | 2 | Required execution, mapping, integrity, or provenance evidence is missing or contradictory. |
| `UNSUPPORTED_TARGET` | 2 | Deterministic preflight proves the scenario, catalog ID, adapter, or target shape is outside the alpha. |

Transport success is not execution success. Completed execution with invalid provenance is not a
behavioral claim. Model prose cannot upgrade either case.
An accepted catalog target whose exact-tree anchor has zero, multiple, or invalid mappings is
`EVIDENCE_INCOMPLETE`, not `UNSUPPORTED_TARGET`; CrashCheck publishes the failed mapping receipt.

## Model and isolation roles

For CrashCheck's future live contract role, Nemotron may turn bounded base-only context into typed
catalog proposals; that call may not emit commands, probes, SQL, assertions, or verdicts.
CrashCheck does not yet call Nemotron in its CLI, and its contract adapter is contract-tested with
injected clients only. The inherited differential live path has a separate generator that may emit
schema-, path-, import-, and assertion-restricted Pytest files, but no current-tree live receipt
exists.

ConTree supplies isolated prepared and branched worlds for the inherited differential live path.
CrashCheck's ConTree transport is not implemented, so untrusted candidates and CrashCheck live mode
remain blocked even when credentials exist. A provider operation ID never substitutes for guest
tree, event, database, worker, execution, and capsule identities.

## Alpha boundary

Supported: Python 3.12+, POSIX process groups and `SIGKILL`, SQLite WAL with
`synchronous=FULL`, the fixed trusted `CreditStore` adapter, `sqlite-credit-v1`, exact fixture/local
directory/Git sources, and trusted owner checkouts.

Unsupported: arbitrary languages, databases, side effects, handlers outside the fixed adapter
shape, hostile local fork execution, generalized schedule or interleaving search, model-authored
code, repair generation, PR comments, and a hosted control plane.

## Claim ledger

| Claim | Implementation | Executable check | Truth / exact evidence |
| --- | --- | --- | --- |
| Real durable checkpoint, process-group kill, fresh replay worker, identical event | `sqlite_credit.py`, `crashcheck.py` | `test_sqlite_credit.py`, `test_crashcheck.py` | `LOCAL` / `FIXTURE`; [successful workflow at exact `f05ae921cf3d866f69adf8415d6d7bd52071bf37`](https://github.com/Alex-lop/Nemisis/actions/runs/33348963355) |
| Candidate-blind two-hypothesis selection before candidate materialization | `crashcheck.py` | candidate-invariance and hunt tests | Same exact workflow above |
| Sole crash action is necessary for this capsule | `crashcheck.py`, `crash_models.py` | deletion, freshness, and tamper tests | Two fresh no-fault confirmations; not a general minimizer |
| Five fresh worlds per claimed tree and scoped verdicts | `crash_models.py`, `crashcheck.py` | role and verdict model/integration tests | Same exact workflow above |
| Portable capsule, manifest, report, regression, and replay | `_publish`, `report.py` | artifact relocation/export/replay tests | Same workflow includes installed-wheel replay |
| Composite GitHub Action | `action.yml` | local Action job plus release tests | GitHub-hosted at the same exact SHA; expected candidate rejection is exit 1 |
| Measured benchmark and one-minute viewer | `benchmark.py`, `docs/assets/crashcheck-hero/` | benchmark and static evidence-binding tests | `LOCAL` / `FIXTURE`; source `ddaf186aa81b8a7ebd442da1f2dfeee6878e7dce`, capsule `1025d9c6…` |
| Nemotron and ConTree adapters | `nemotron.py`, `contree.py`, `live.py` | injected-client contract tests | `MOCKED`; genuine current-tree path is `BLOCKED` |

No fixture, mock, historical result, or local run may be relabeled as live evidence. Genuine live
claims require sanitized receipts bound to the exact source SHA, capsule digest, model, endpoint,
provider worlds and operations, and guest execution identities, with transport, execution,
provenance/integrity, and behavioral verdict reported independently.
