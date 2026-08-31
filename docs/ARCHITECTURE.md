# Architecture

Nemisis has two deliberately bounded, additive execution surfaces with shared evidence rules.
Models may propose bounded inputs; deterministic code owns validation, execution, classification,
and final artifacts.

## Differential verifier

`nemisis verify` implements the original claim-matrix workflow:

1. `VerificationRequest` binds ticket, base, candidate patch, runtime mode, and limits.
2. `VerificationBundle` binds baseline and adversarial tests, trusted harness files, Pytest command,
   parser digest, dependency identity, model/prompt identity, and one bundle digest.
3. Local or ConTree orchestration derives base and candidate worlds from one prepared source. Only
   the candidate world receives the validated patch.
4. The same bundle bytes run in both worlds. A bounded JUnit parser maps each expected test to
   `PASS`, `ASSERTION_FAIL`, `ERROR`, `TIMEOUT`, or `NOT_RUN`.
5. Matrix code alone evaluates `CHANGE_WITNESS` and `INVARIANT`; incomplete outcomes fail closed.
6. `RunManifest` binds the request, worlds, receipts, matrix, artifact decision, and source commit.

Local verification uses real temporary filesystem copies and subprocesses but checked-in claims and
tests, so its truth label is `FIXTURE`. The live adapter performs a Nemotron call and derives
persistent common/base/candidate ConTree images for the same audited fixture.

## CrashCheck

CrashCheck is a second, narrower projection for stateful crash/retry evidence, not a replacement for
the claim matrix. Its Python surface is:

```python
initialize(issue, target, base, scenario_id) -> Path
check(base, candidate, scenario, corrected=None, mode="local") -> CrashCheckResult
replay(capsule, source, role="candidate", mode="local") -> CrashCheckResult
```

The core records are:

- `RetryContract`: accepted issue/base/target binding and trusted event, fault, probe, and predicate
  catalog IDs.
- `AnchorBinding`: handler mapping plus supplied source ref, resolved source identity, and exact tree
  digest.
- `HypothesisReceipt`: one candidate-blind base attempt, its fixed crash boundary and canonical
  rank, exact contract/base/provisional-capsule bindings, observation, and selection decision.
- `MinimizationReceipt`: one fixed deletion trial for the selected one-action schedule, including
  two fresh empty-schedule base confirmations and the stable necessity decision.
- `AttemptReceipt`: transport, integrity, process-group kill, two worker spawns, nonces, IPC
  sessions, durable snapshots, logs, and optional provider identifiers.
- `ReproCapsule`: stable contract, event, selected semantic fault boundary, predicates, environment,
  trusted-engine code digest, and the single-action deletion trace; volatile PIDs, paths,
  timestamps, full hunt attempts, and per-tree anchors stay outside it.
- `CrashCheckResult`: both hypothesis receipts, exact role bindings and confirmations, independent
  execution/integrity axes, scoped verdict, engine digest, and root-relative artifacts.

For ordinary Git refs, the resolved identity is the full commit SHA. Fixture refs retain their
fixture identity. A local directory is copied and identified by its tree digest. `.git`, `.nemisis`,
`__pycache__`, `.pytest_cache`, and `.mypy_cache` are excluded consistently from local copies and Git
archives before hashing.

## Candidate-blind hunt and confirmation

`check` materializes and binds the accepted base before it reads or materializes the candidate. It
then runs exactly two fixed hypotheses in parallel base-only worlds:

1. `effect-commit-v1` pauses at the first probe showing one durable credit effect.
2. `marker-commit-v1` continues past earlier commits until one durable effect and one marker are
   visible.

Each world produces a real `AttemptReceipt`, wrapped by a canonically ranked
`HypothesisReceipt`. After filtering to completed, integrity-valid duplicate observations, the
smallest fixed catalog rank wins; parallel completion order is irrelevant. In the packaged buggy base,
`effect-commit-v1` reproduces and `marker-commit-v1` does not. Their stable projections are stored
in `hunt.json`, not in the capsule trace. CrashCheck then deletes the selected schedule's sole fault
action in two fresh base worlds. Both empty-schedule replays finish exactly once, so deletion is
rejected and the capsule binds only that stable one-action necessity decision. Volatile hunt and
deletion receipts remain outside the content address. Five new base worlds reconfirm the retained
witness before the candidate is materialized.

The hunt receipts are discovery evidence, not confirmation runs. A conclusive verdict separately
requires five fresh attempts for every claimed role, with globally unique database, execution,
worker, and IPC identities. The three-tree hero therefore records two hunt attempts, two deletion
confirmations, then five base, five candidate, and five corrected confirmations.

## CrashCheck kernel

The current adapter accepts one synchronous two-argument Python handler using the trusted
`CreditStore` API:

1. Prepare a closed SQLite seed using integer cents, WAL, and `synchronous=FULL`.
2. Spawn the handler in a controller-owned process group and IPC session.
3. Pause at the capsule's selected semantic boundary and independently probe the durable effect and
   marker state.
4. Send `SIGKILL`, wait for `-SIGKILL`, and confirm durable state did not change.
5. Spawn a fresh worker with a new nonce/session and replay identical event bytes.
6. Probe the final balance, ledger count, and marker count. Any missing or contradictory evidence
   makes the attempt incomplete.

At `effect-commit`, the buggy and misleading-green trees expose one effect with no marker and reach
`$50` after replay. The atomic tree reaches the same semantic effect boundary with its marker
already durable and remains at `$25` with one effect and marker.

## Provider boundary

Token Factory inference defaults to the official global endpoint
`https://api.tokenfactory.nebius.com/v1/` and
`nvidia/nemotron-3-super-120b-a12b`. URL validation permits only official Nebius global/regional
HTTPS `/v1` endpoints. ConTree is constructed from its official saved profile, uses an immutable
root-image UUID, fixed commands/arguments, disabled networking, bounded streams, and persistent
image receipts.

The live differential verifier currently supports only `idempotency-retry`. Its JUnit XML is
written inside the guest and returned through bounded stdout; the parser and exact bundle binding
detect malformed or incomplete results, but this is not a provider-owned test attestation. That
trust boundary is not advertised for arbitrary repositories.

CrashCheck's local kernel is integrated; its ConTree provider transport is explicitly unimplemented.
A requested CrashCheck live run returns `EVIDENCE_INCOMPLETE`/`UNSUPPORTED`, names the doctor
blockers, and never substitutes local execution—even if credentials are present.

## Artifacts and projections

Differential manifests/reports live beneath `.nemisis/runs/`. CrashCheck stores root-relative
artifact references and adds `.nemisis/repros/double-credit/<capsule-digest>/` for the immutable
capsule, event, accepted contract, hunt metadata, and regression asset. The directory name is the
capsule's canonical content digest, so the repro can be moved with its artifact root without
embedding host paths. Every run has a manifest under `runs/`; attempt-bearing runs also have a
report, while pre-execution anchor failures have `anchor-resolution.json`. The CLI, static reports,
and composite action display stored evidence and do not derive independent verdicts.

There is no repair generator, plugin framework, arbitrary assertion language, executable config,
web server, or provider fallback in the current tree.
