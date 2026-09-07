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
outside candidate-controlled paths, and its digest is verified before the world runs. The ConTree
runner re-hashes the bundle and the workspace after execution and fails closed if either changed;
local `verify` re-hashes the candidate world, not the bundle. Candidate changes to its own tests or
Pytest configuration do not become acceptance evidence.

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

The controller, fixed hypothesis catalog, the scenario objects and their stores (`CreditStore`,
`InventoryStore`), socket protocol, read-only probe, contract/capsule validators, source binder,
SQLite runner, verdict derivation, display formatting, and report renderer are trusted. Their installed source/catalog bytes are hashed into `engine_code_digest`, which is
required by both the capsule and result and validated before replay execution. Issue text,
repository content, refs, config imports, capsules, IPC messages, logs, and provider responses are
untrusted inputs.

The controller owns the process group, socket, execution nonce, and IPC session. It requires the
expected durable checkpoint, sends `SIGKILL`, waits for exit `-9`, probes again, and spawns a new
worker with a distinct nonce/session for replay. Surviving descendants are detected by the worker's
inherited stdout/stderr pipes staying open and are killed with the group; a handler that forks,
calls `setsid`, and closes those pipes escapes that detection. That is inside the stated boundary
(local mode is for a trusted checkout, not hostile code) and such a run still fails closed on its
contradictory receipts rather than proving anything. SQLite state is outside the source tree, uses
integers (cents, units), WAL and `synchronous=FULL`, and is observed through fresh read-only
connections.
Failure to launch, checkpoint, kill, wait, probe, restart, replay, parse, or clean up makes evidence
incomplete.

Every durable change the controller can read is attributed, at the level of the whole database
file and of the file itself. The worker reports each trusted store commit by operation name; the
scenario predicts the database content after that operation (every row of every seeded table,
with its rowid); the kernel adds the schema (`sqlite_master`), the header fields a commit never
changes (journal mode, the schema cookie, the free-page count, page size, vacuum mode, encoding,
`default_cache_size`, `user_version`, `application_id`), and the file's own identity (its 100-byte
header, except the three fields a commit rewrites, and its length, which must be exactly the page
count its header states), reads all of it at that instant, and refuses anything that differs; it
reads again after the kill and after the worker's final message. The seed leaves the file in WAL
mode so the journal bits are constant for the run. A handler that moves money through its own
SQLite connection, creates a table for its dedup flag, stores a flag in a header field (read or
reserved), in a rowid, in the free-page count, or in bytes past the last page, re-points a ledger
row, or renames and replaces a table therefore cannot earn a verdict. If it also makes a store
commit, the unattributed content is caught at the next probe and the run is `INTEGRITY_ERROR` /
`INVALID`, because the kill point could no longer be trusted to sit where the money moved. If it
makes no store commit at all, which is what the textbook atomic fix written as one raw transaction
does, there is no kill point to place: the run is `CHECKPOINT_NOT_REACHED`, the verdict is
`EVIDENCE_INCOMPLETE`, and the summary names the write it saw and the store call that expresses
the same fix. Two hostile reviews on 2026-09-06 found eleven such channels that an earlier engine
blessed, and a third on 2026-09-07 found thirty-seven more (a header field the probe never read,
the reserved header bytes, bytes past the last page, a file flag, an extended attribute on the
platform where the guard was inert, the mode and modification time of the world's own
directories, a HOME removed or replaced, a directory made unlistable, a scratch-tree whitelist
built from names, the trusted store patched at import); each is pinned in
`tests/test_verdict_paths.py`. The worker compares the trusted store's and protocol's code objects
before and after the handler module is imported, so a module that rebinds a store method to one
that under-reports its commits is refused as `TrustedStorePatched`.

What the controller cannot read, it does not claim. These stay outside what local mode can see,
and are the honest list: a flag the store's own next commit overwrites (the database file's
modification time, the bytes of the WAL sidecar); a flag at the sidecar names the store owns
(`<database>-wal`, `<database>-shm`), whose presence after a kill a handler can also read as "the
last delivery crashed"; a write through a private connection that is reverted before the next
store commit, because attribution samples the database at commits and not between them (the kill
points are store commits, so such a window is one CrashCheck never claimed); a handler that reads
CrashCheck's scratch tree and counts the worlds of its phase, which tells a census from a kill
world; and durable state kept elsewhere on the machine by absolute path. A handler that forges the
IPC message on the store's private channel, or patches the interpreter below the store, is hostile
code, which local mode does not claim to contain.

Kill points are store commits, and only store commits. Each world runs in its own directory: the
worker's cwd sits two levels inside it, and `HOME` and `TMPDIR` point inside it too. The kernel
records the permission bits, file flags, extended attributes, and (for every directory but the
cwd, where SQLite's sidecars come and go) the modification time of the world's directories when
it makes them, and of the database file when it seeds it. That directory is scanned right after
the kill (before a replay could tidy a flag away), between the census's two deliveries, and at the
end, by the kernel's own walk, which refuses a directory it cannot list; it may hold nothing but
the database and its WAL sidecars, every recorded entry must still exist as what it was with the
metadata it had, and the database file must keep the seed's mode, flags, and attributes. A file,
an empty directory, or a journal written anywhere in it (beside the database, one or two
directories up, under `~`, or under the temp directory) forfeits the verdict, because a crash
window around that state is one no store commit can reach. The bound source tree is compared
entry by entry, bytecode caches and directories included, before and after every delivery. The
run's scratch root holds the source copies and the phase roots the kernel made, by recorded
identity and not by name: after every phase, every source copy and every finished phase is
re-checked entry by entry and the root may hold nothing else, or the run stops without a verdict
and names the entry. Durable state kept elsewhere on the machine, by absolute path, is outside
what local mode can see and is a documented boundary, not a claim; a handler whose commit
schedule differs between the kill worlds and the census is `EVIDENCE_INCOMPLETE`, never swept, and
the sentence says only what it saw. Every world is named by an opaque identifier and nothing in
its path or environment names a role or a phase; a handler that reads outside its world can still
count its siblings, which is the boundary of in-process instrumentation on a shared filesystem.
It can also tell that it is inside CrashCheck (the store object is in its hands): a handler that
is correct only when it detects the harness is hostile code, and local mode assumes a trusted
checkout.

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
endpoint; ambiguous hosts, credentials in URLs, non-default ports, and query strings are rejected
before any request is made. Nemisis does not itself refuse redirects: the provider SDK's HTTP client
follows them, and only its cross-origin rule strips the credential header. ConTree authentication
and service selection come from the standard `contree-client` profile rather than candidate input.
Provider operation/image identities remain separate from guest tree, process, database, and test
evidence.

A result is `LIVE` only with genuine sanitized current-tree receipts. `RECORDED_LIVE` is reserved
for prior genuine evidence and is refused when a config file supplies it; no code path in the tree
emits that label. Injected clients remain `MOCKED`; audited checked-in content is `FIXTURE`.
CrashCheck's provider transport is explicitly unimplemented, so live CrashCheck remains blocked even
if credentials, profile, and immutable image are supplied. Its incomplete live receipt cannot be
upgraded by local execution.

## Supported claims

Differential success means only that declared relations were supported by the observed bundle in
the exact worlds. CrashCheck success means only that one exact source defeated one frozen capsule
while its observed invariants passed. Neither is formal verification, vulnerability freedom,
general retry safety, safe execution of arbitrary code, or a universal merge recommendation.
