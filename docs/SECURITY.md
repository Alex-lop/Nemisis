# Security boundary

Nemisis executes repository and model-generated Python. Its safety claim is deliberately narrower
than a general hostile-code sandbox.

## Shared authority rules

- Models may propose bounded claims/tests or audited catalog selections; deterministic code validates
  them and owns acceptance.
- Candidates cannot choose commands, parsers, truth labels, environment variables, mounts, network
  destinations, state probes, or verdict logic.
- Strict models reject extra fields; canonical SHA-256 digests bind accepted content and evidence.
- Diagnostics inspect only credential presence/capability. Live adapters may send credentials only
  to their configured official service; neither path persists them in logs, manifests, reports,
  fixtures, or committed receipts.
- Missing, malformed, timed-out, or contradictory evidence fails closed and never triggers a live to
  local fallback.
- A Nemotron contract proposal is provenance, not evidence. The model sees only issue text and the
  base handler, may return only offered catalog IDs and one bounded scalar, is accepted or refused by
  fixed rules before any draft, and is attached to a check only when its receipt binds the exact
  contract identity. A malformed sidecar fails closed; a foreign one is ignored. The receipt never
  contains the credential, the issue, the handler source, or the raw response.

## Differential verifier

The trusted verification bundle includes baseline/generated test bytes, a Nemisis-owned Pytest
plugin, fixed runner argv, parser identity, dependency identity, and one digest. It is materialized
outside candidate-controlled paths and checked before and after execution. Candidate changes to its
own tests or Pytest configuration do not become acceptance evidence.

Generated tests are schema-, path-, count-, size-, syntax-, name-, and import-restricted. The model
cannot return commands or runner configuration. Local `verify` accepts only the checked-in trusted
fixture; it is not safe arbitrary-code isolation.

The ConTree verifier uses an immutable root image, fixed commands/arguments, disabled networking,
bounded output, persistent image identities, and byte-identical bundle uploads. The current ConTree
client returns guest-written JUnit through guest stdout/files rather than a provider-owned result
attestation. Exact expected IDs, markers, exit status, bundle/tree digests, and report bounds are
validated, but this channel remains limited to the audited `idempotency-retry` fixture and validated
generated tests.

## CrashCheck trusted computing base

The controller, fixed hypothesis catalog, `CreditStore` adapter, socket protocol, read-only probe,
contract/capsule validators, source binder, SQLite runner, verdict derivation, and report renderer
are trusted. Their installed source/catalog bytes are hashed into `engine_code_digest`, which is
required by both the capsule and result and validated before replay execution. Issue text,
repository content, refs, config imports, capsules, IPC messages, logs, and provider responses are
untrusted inputs.

The controller owns the process group, socket, execution nonce, and IPC session. It requires the
expected durable checkpoint, sends `SIGKILL`, waits for exit `-9`, probes again, and spawns a new
worker with a distinct nonce/session for replay. SQLite state is outside the source tree, uses
integer cents, WAL and `synchronous=FULL`, and is observed through fresh read-only connections.
Failure to launch, checkpoint, kill, wait, probe, restart, replay, parse, or clean up makes evidence
incomplete.

Exactly one trusted, tree-bound `AnchorBinding` must validate. Candidate output cannot acknowledge
success or authorize an anchor.

The candidate is not materialized until the base hunt, deterministic selection, one-action
necessity check, and five fresh base confirmations have frozen the witness. The hunt accepts exactly
the fixed `effect-commit-v1` and `marker-commit-v1` base-only hypotheses. Each `HypothesisReceipt` is bound to
the contract, originating base tree, provisional capsule, and a real base attempt; ranks, boundary,
operation count, reproduction flag, and selection must match the catalog. Hunt database, execution,
worker, and IPC identities must be disjoint from later confirmation identities. Candidate bytes,
refs, digests, paths, mappings, receipts, and cache keys have no input seam into this phase.

Full hunt and deletion-confirmation receipts include volatile execution facts and therefore remain
outside the capsule's content address. After selection, CrashCheck removes the schedule's sole
fault action and runs the empty schedule in two fresh base worlds. Exactly-once twice rejects that
deletion and proves only that the one action is necessary for this fixture witness; it is not a
general minimizer. The capsule binds the stable decision digest while the result retains the full
receipts. A conclusive result still requires five completed, valid, globally fresh confirmation
attempts for every claimed role; hunt and deletion attempts cannot satisfy that count.

## Source and artifact containment

Git refs resolve to full commit SHAs; fixture refs retain their immutable fixture identity; local
directories resolve to the copied tree digest. Bindings record both the supplied ref and resolved
identity. `.git`, `.nemisis`, `__pycache__`, `.pytest_cache`, and `.mypy_cache` are excluded before
hashing so local evidence and caches cannot affect source identity.

Input paths must be contained beneath allowed roots. Traversal and symlink escape are rejected;
archives are file-count/byte-bounded and materialize only regular file members; writes outside the
trusted artifact root are rejected. Evidence stores artifact-root-relative paths, and a repro
directory is addressed by the canonical capsule digest. Its sibling accepted contract, event, hunt
metadata, capsule, and regression asset are sufficient to relocate and validate the export without
retaining a host path. Existing content cannot be silently overwritten with different bytes. HTML
escapes untrusted text; GitHub summaries indent command output.

## Local and GitHub execution

Local execution is only for a trusted owner checkout. The example workflow uses `pull_request`,
read-only contents permission, credential-free checkout, a fresh `${{ runner.temp }}` directory, and
no PR comments. It refuses untrusted forks before checkout/execution, exits `2`, and writes an
`EVIDENCE_INCOMPLETE` job summary without creating a CrashCheck manifest. Running an untrusted
public candidate requires CrashCheck ConTree isolation, which is not implemented.

Pin the Nemisis composite action and all third-party actions to reviewed full commit SHAs. Accepted
configuration is loaded from the exact base commit, not a candidate replacement.

## Provider and credential separation

Token Factory credentials may be sent only to an official Nebius HTTPS `/v1` global or regional
endpoint; ambiguous hosts, credentials in URLs, non-default ports, query strings, and redirects are
rejected. ConTree authentication and service selection come from the standard `contree-client`
profile rather than candidate input. Provider operation/image identities remain separate from guest
tree, process, database, and test evidence.

A result is `LIVE` only with genuine sanitized current-tree receipts. Prior genuine evidence is
`RECORDED_LIVE`; injected clients remain `MOCKED`; audited checked-in content is `FIXTURE`.
CrashCheck's provider transport is explicitly unimplemented, so live CrashCheck remains blocked
even if credentials, profile, and immutable image are supplied. Its incomplete live receipt cannot
be upgraded by local execution.

## Supported claims

Differential success means only that declared relations were supported by the observed bundle in
the exact worlds. CrashCheck success means only that one exact source defeated one frozen capsule
while its observed invariants passed. Neither is formal verification, vulnerability freedom,
general retry safety, safe execution of arbitrary code, or a universal merge recommendation.
