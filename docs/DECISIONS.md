# Decisions

## CrashCheck and differential verification are additive products

The original deterministic differential verifier remains available unchanged: identical trusted
bundles, exact base/candidate worlds, typed relations, and model-independent classification.

CrashCheck is a separate narrow stateful product because crash/retry bugs need evidence an ordinary
test matrix cannot make visually causal: durable effect, real worker death, fresh process, identical
replay, final durable state. Neither path replaces or wraps the other; their matrix and capsule
semantics remain explicit.

## One real SQLite crash/retry proof

The first CrashCheck case is `sqlite-credit-v1`: expected account credit `+$25`, observed `$50` after
worker death and retry. A real process-group `SIGKILL`, confirmed exit, fresh spawn/nonce/session, and
independent durable probes are mandatory. A raised Python exception is not equivalent evidence.

The benchmark executes the ordinary repository test and sequential duplicate check to explain why
the candidate looks plausible. Those measurements are context, not CrashCheck hunt or confirmation
receipts.

## Semantic capsule and exact source bindings

The capsule freezes semantic event/fault/predicate/runner identities, not a source line. Each
`AnchorBinding` separately records the supplied ref, resolved full commit/fixture identity, tree
digest, and one trusted handler mapping. A source outside the catalog is `UNSUPPORTED_TARGET`; an
accepted catalog target whose exact tree yields zero, multiple, or invalid mappings publishes
structured `EVIDENCE_INCOMPLETE` evidence instead of guessing.

Run output, `.git`, `.nemisis`, bytecode, and local pytest/mypy caches are excluded before source
hashing. This prevents local evidence from changing the source it claims to evaluate and avoids a
self-referential committed configuration digest.

## Candidate-blind CrashCheck ordering

CrashCheck binds the accepted issue/base contract and runs exactly two parallel, fixed, base-only
crash-boundary hypotheses before it materializes the candidate: `effect-commit-v1` and
`marker-commit-v1`. Full attempt receipts are preserved. After both are terminal, selection filters
to completed, integrity-valid duplicate observations and chooses the smallest fixed catalog rank.
The selected semantic boundary and stable one-action deletion decision freeze the capsule;
candidate content cannot change the hypothesis ranking, event, fault schedule, probes, parser,
harness, or verdict.
The deletion check proves necessity only for this fixture witness; it is not a general schedule
minimizer.

The hunt does not count as proof replay. After selection, five new base worlds must reproduce before
candidate materialization; each later claimed candidate or corrected role also requires five fresh
worlds. The checked-in audited contract is `FIXTURE`; another local contract requires explicit
digest acceptance.

The bounded Nemotron contract adapter may select only audited catalog IDs and in-range scalars.
`init --nemotron` puts it on the CrashCheck CLI path as provenance for a draft; see the decision
below. No live generation is claimed until a genuine receipt exists.

## Nemotron plays the coding agent, never the judge

The thesis is that AI-written retry patches look green and still lose money. The honest,
load-bearing job for NVIDIA's model is therefore to write the patch. `nemisis propose-patch` gives
Nemotron the bug report, the base module, and the storage API, and nothing else: no kill points, no
catalog, no verdict rules. Its module is accepted only after deterministic AST checks (one
synchronous `(store, event)` handler, imports from `typing` and `__future__` only, no private names
or attributes, no dangerous builtins, no `global` or `nonlocal`) and is then an ordinary candidate
tree. The authorship receipt is provenance in the manifest and report; the verdict comes from
executing the tree. This keeps the authority model intact: the model proposes the thing under test,
deterministic code decides what happened to it.

Without a `NEBIUS_API_KEY` the command exits `2` and writes nothing. Injected clients yield a
`MOCKED` receipt, which the report labels as such. No `LIVE` authorship receipt exists in this tree.

## Nemotron proposes at init, never at check

The model's one CrashCheck role is to turn the issue and the exact base handler into a typed
catalog proposal with one bounded scalar before any candidate exists. Fixed rules accept it only
when it selects the audited fault intent and the exact expected effect; a mismatch drafts nothing
and prints the model's values, so the call is load-bearing rather than decorative.

The receipt lives beside the contract in `.nemisis/proposal.json` instead of inside it. A contract
digest must stay a semantic identity (catalog IDs, issue, base tree, target) so the packaged
`FIXTURE` contract and a user's accepted copy hash identically; a receipt carries timestamps and
latency that would perturb that digest. `check` attaches the sidecar only when it is accepted and
binds the same scenario, target, issue digest, and base tree digest; a foreign receipt is ignored
and a malformed one fails closed. The proposal never enters the capsule address or the verdict.

## Strict JSON and fixed trusted runners

Configuration, manifests, receipts, and capsules use strict canonical JSON. The differential
verifier owns its Pytest argv, plugin, result parser, and full bundle. CrashCheck owns its adapter,
socket protocol, state probes, and verdict rules. Neither model output nor candidate configuration
may supply a command, parser, probe, SQL statement, or verdict.

CrashCheck additionally hashes the installed trusted engine and catalog resources into an
`engine_code_digest` carried by capsule and result. A source-commit label remains useful provenance,
but it does not replace the byte digest and may be absent outside a Git checkout.

## Portable content-addressed repros

The capsule digest addresses immutable repro assets. Artifact references are relative to the chosen
artifact root, and the export carries its accepted contract, event, hunt metadata, capsule, and
regression test together. Volatile hunt PIDs, nonces, timestamps, logs, and absolute host paths do
not enter the capsule address. This makes identical semantic evidence stable across output roots and
lets a custom accepted-contract repro validate after relocation.

## Static reports and a composite action

The existing static renderers are enough for matrices and recorded timelines. A web server or React
application would add deployment and trust boundaries without strengthening current proof.

The GitHub integration is a composite action plus copyable `pull_request` workflow. It uses a
base-owned accepted config, exact candidate checkout, read-only permissions, a runner-temporary
artifact root, job summary, and upload. PR comments remain deferred.

## Known-good control, not repair generation

The packaged CrashCheck proof supplies an exact atomic revision so one capsule can demonstrate both
negative and positive outcomes. Nemisis exports the regression asset but does not generate or apply
a repair in this slice.

## Preserve one supported scenario after the viewer

Superseded on 2026-09-06 by "The second scenario is a decrement, not a renamed credit". At the
time of this decision the sprint kept `sqlite-credit-v1` as the single supported CrashCheck slice.
A second adapter would not have closed the missing live transport, exact sponsor receipt, public
hosting, or demo-video gates, and would have added a new trust surface before a second consumer
was justified.

## Depth before width: the commit sweep instead of a second scenario (2026-09-05)

The overnight hardening had the choice again and chose depth. Red-teaming the checker with thirty
adversarial handlers found two false passes inside the one supported scenario; fixing them (kill
after every store commit of a claimed fix; attribute every durable change to a reported store
commit) makes the core claim true, which a second scenario would not have done. A judge who can
write a handler in thirty seconds (`nemisis export`) and watch it fail for the right reason is
harder to dismiss than one shown two look-alike scenarios.

A second scenario is still the right next seam. It is not a plugin today. The hardcoded points are:

- `sqlite_credit.py`: the catalog constants (`_SCENARIO_ID`, `_ADAPTER_ID`, `_FAULT_ID`,
  `_PROBE_ID`, `_PREDICATE_ID`, `_TARGET`), `_SCHEMA`, `_seed_database`, `_probe`, `_event`
  validation, `_wait_for_checkpoint`'s effect condition, `_STORE_DELTAS`, and `CreditStore`;
- `crash_models.py`: `CreditSnapshot`'s four fields, `classify_final`, the capsule's
  `event_id`/`account_id`/`amount_cents`, and `amount_cents` on the receipts;
- `crashcheck.py`: `_seal_capsule`, `_validate_capsule_contract`, the `repros/double-credit/`
  path, the money and `evt_1042` wording in summaries, and `_regression_asset`;
- `report.py` and `cli.py`: `money()` and credit labels; the viewer reads `account_balance_cents`.

A real seam is a `Scenario` object supplying ids, schema, seed, store class, event shape, probe,
allowed deltas, checkpoint predicate, `classify_final`, and display labels, with a generic
four-field snapshot whose field names do not lie about their contents. Budget half a day with the
gate, plus one hero and benchmark regeneration. Do not ship it as a renamed copy of the credit
fixture; the second scenario must have its own seed, effect direction, and predicate.

## Official live endpoints and narrow trust

Inference defaults to `https://api.tokenfactory.nebius.com/v1/` and
`nvidia/nemotron-3-super-120b-a12b`. Overrides are accepted only for the official Nebius global or
regional HTTPS `/v1` host pattern. ConTree comes from the official profile and an immutable image
UUID; there is no generic provider layer or automatic fallback.

Only the original `idempotency-retry` verifier is connected to ConTree. CrashCheck's own Nemotron
calls are the bounded contract proposal (`init --nemotron`) and `propose-patch`, and both are
provenance beside the verdict rather than input to it. The verifier's JUnit XML is guest-produced
bounded evidence, not provider-owned attestation, so arbitrary repositories remain unsupported.
CrashCheck live provider transport is explicitly unimplemented; it remains blocked even when
external credentials and image prerequisites are otherwise satisfied.

## Published low-level ConTree client

Pin `contree-client[httpx]==0.3.0`. When selected, the documented high-level SDK interface was not
available in a published `contree-sdk` build, while the official low-level client exposed the image,
operation, file, stream, and metrics receipts required by the verifier. Revisit this seam when the
published high-level interface provides equivalent evidence.

## The Scenario seam (2026-09-06)

The hardcoded points listed above now read from one object, `nemisis.scenario.Scenario`. Its
instances are `nemisis.scenarios.sqlite_credit_v1.SCENARIO` and
`nemisis.scenarios.sqlite_inventory_v1.SCENARIO`, and the kernel resolves a scenario id against the
registry in `nemisis.scenarios`. A scenario supplies the catalog ids, the target, the packaged
resources and their pinned digests, the SQLite schema and seed, the trusted store class the handler
is handed, the delta each store operation may make (attribution), the event shape and its
normalization, the checkpoint predicate, the effect delta the verdict rule uses, the repro
directory name, and the words a summary prints. The kernel in `sqlite_runner.py` and
`crashcheck.py` reads the scenario and special-cases nothing; the worker is told the scenario id on
its command line and constructs the scenario's store. The scenario modules are trusted engine
resources and enter the engine code digest.

The seam landed in two steps. The first changed no behavior: every packaged tree kept its verdict,
exit code, and summary, and the capsule and hunt contents were identical apart from the engine and
runner digests that cover the moved bytes. The second made the receipts generic so a second
scenario could be honest: `CreditSnapshot` became `StateSnapshot` (`subject_total`,
`event_effect_count`, `event_effect_total`, `event_marker_count`, names that say what they hold for
a balance or a stock level), `amount_cents` on the receipts became the signed `effect_delta` one
delivery makes, the capsule carries its whole `event` plus `event_id` and `effect_delta` instead of
credit fields, `classify_final` takes the delta and the seeded total, the contract proposal names
its scalar, and the CLI and report ask the scenario how to print its quantity. The runner was
renamed `sqlite_runner.py` (runner id `sqlite-runner-v2`) because it no longer knows about credits.
The committed hero was recorded under the old shape; `tests/test_static_hero.py` checks it
structurally until it is regenerated at this engine.

## The second scenario is a decrement, not a renamed credit (2026-09-06)

`sqlite-inventory-v1` reserves two units of a SKU for an order: stock 10 becomes 8, the buggy
handler is check, decrement, mark, a kill after the decrement and a retry oversell to 6, and
exactly once is one reservation row, one marker, eight on hand. It has its own seed (not zero),
its own effect direction (the subject goes down), and its own predicate, which is what forced the
receipts generic. It is the same bug the original differential verifier's `idempotency-retry`
fixture leaves `UNRESOLVED`, so the row the old product could not decide is the second thing the
new product proves. It ships with buggy, misleading-green, atomic, and mark-first trees, its issue
text, a README row, and a wheel smoke in CI. The CLI infers the scenario from a fixture base ref;
an explicit mismatch is refused with the flag to pass.

## CI red-teams the checker every run (2026-09-06)

The hardening night red-teamed the checker by hand with fifty-five agent-written handlers and
packaged three. `nemisis redteam` turns that into a generator: a grammar over store operations
(guard, credit, mark, the atomic call, a raw file beside the database, a raw SQL write) renders
handler modules, `check` judges each, and an oracle that only knows the operation sequence (what
each store call does to the durable state, where a kill can land, that a write around the store
forfeits the verdict, that a second marker raises) names the verdict the checker must return. The
oracle is pinned on the packaged credit trees its grammar can express and on the hardening night's
shapes; ten fixed-seed cases run in the normal suite and a nightly workflow runs three hundred. The
grammar is credit-shaped, so `sqlite-inventory-v1`'s trees are covered by their own tests rather
than by the oracle. A disagreement fails the run and is either a checker false pass or false fail,
the most valuable bug this repository can find, or an oracle bug. The generator is deliberately
outside the trusted engine: it writes candidates and reads verdicts.

## Attribution is the whole database and the whole world (2026-09-06)

A hostile review of the night's engine found five handlers that earned
`FIX_PROVEN_FOR_THIS_CAPSULE` while a crash in a window no store commit can reach lost or moved
the money: dedup state in a table the handler created inside the store's own file, a flag in
`PRAGMA user_version`, a dedup file one directory above the worker's cwd, an empty directory as
the flag, and a ledger row re-pointed at another account after the atomic commit (plus a renamed
and replaced `accounts` table). One root cause: attribution watched four numbers in three tables
and the file guard watched one directory. Now the scenario predicts the entire database after each
reported store operation (every row of every seeded table, plus the schema and the header pragmas
the kernel adds), the controller reads the entire database and refuses any difference, and each
world runs in its own directory with the worker's cwd two levels inside it and `HOME` and
`TMPDIR` inside it too; after the run that directory may hold nothing but the database and its
WAL sidecars. Durable state by absolute path elsewhere on the machine remains a documented
boundary. The table handler ships as `fixture:sqlite-credit-v1/shadow-table`; the others are
pinned as tests. The generator's oracle was unaffected: its grammar has no such op yet.

## What the controller cannot read, it does not claim (2026-09-06, after the second review)

The review of the whole-database fix wrote seven more handlers that still passed: a flag in the
journal-mode header bits (the store's own first connection used to flip them), a rowid, the
free-page count after `CREATE` and `DROP TABLE`, the schema cookie, a file deleted before exit, a
bytecode-cache file or an empty directory in the bound tree, the database's own permission bits,
a file at the `-shm` name, and `../../..` into the shared scratch tree. Structural answers landed
for all but two: the seed stays in WAL; the header read covers every durable field a commit never
touches; rowids are read and modelled; the crashed world is scanned right after the kill and the
census world between its deliveries; the file's permission bits and extended attributes must be
the seed's; the bound tree is compared entry by entry; a BLOB is carried as its hex; the scratch
tree may hold nothing but the worlds. Two channels stay open and are written down instead of
claimed away: a flag the store's own next commit overwrites (the file's modification time, the WAL
bytes) and a flag at the sidecar names the store owns. A kill world whose commits are not a prefix
of the census's is refused outright, because that is what hidden state looks like from outside.
The lesson the night leaves behind: in-process instrumentation can attribute everything it can
read; the honest sentence is the list of what it reads.

## The grammar speaks what the reviewers wrote by hand (2026-09-07)

Yesterday's generator could not express a single shape of the eleven the two hostile reviews
found, so its three hundred agreeing cases said nothing about the attribution fix. Every one of
those shapes is now an operation of the grammar, in either scenario's vocabulary: a table or a
pragma inside the store's file, a file beside the database, one directory up, under `HOME` or
under `TMPDIR`, a file tidied away before returning, a re-pointed effect row, a marker inside
`try`/`except` (a second marker is swallowed instead of raised), a retry loop, a helper function
the bound handler calls, and a world-detection attempt that returns early if the world's path or
environment names a census, a sweep, or a role. The oracle learned the two facts the kernel's
probes have: a write inside the database file is seen at the next commit probe, a file in the
world only at a scan, which happens after the kill and after a completed delivery. So a file
written and deleted between two commits was never durable state at a kill point and the oracle
says `FIX_PROVEN`, while `../side.txt` outlives a delete that reaches only the cwd. The
world-detection op is a canary: every world is named by an opaque id, so the op is a no-op today,
and the day an engine change leaks a role into a path or an environment variable the nightly
sweep disagrees with the oracle. A third scenario adds a `Vocabulary`, not a grammar.

## Every wall-clock wait names what did not happen (2026-09-07)

The kernel had one budget, ten seconds, re-armed for each phase of each world, and every expiry
said "worker IPC timed out": the same five words for a hello that never came, a first delivery
that never reached its commit, and a replay that never finished. A base world that timed out was
reported as "the originating base did not reproduce in five fresh worlds", which is false, and
the one flaky observation on record could not be diagnosed from what it printed. The budget is
now a documented knob, `NEMISIS_WORKER_TIMEOUT_SECONDS`, read once before any world runs and
refused outside 1 to 600 seconds (a typo must not widen a wait silently); every expiry names the
phase, the commits seen so far, the budget, and the knob; a base hunt or confirmation whose
worlds did not complete says so, and a base that completes exactly once is told to pass the tree
that still has the bug. The default did not move. A `Soak` workflow repeats the kernel's slow
tests N times on GitHub's Linux, with the knob as an input, so the next flake is found there.
