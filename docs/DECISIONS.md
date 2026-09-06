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
load-bearing job for NVIDIA's model is therefore to write the patch. `nemisis propose-patch`
gives Nemotron the bug report, the base module, and the storage API, and nothing else: no kill
points, no catalog, no verdict rules. Its module is accepted only after deterministic AST checks
(one synchronous `(store, event)` handler, `typing` imports only, no private attributes, no
dangerous builtins) and is then an ordinary candidate tree. The authorship receipt is provenance in
the manifest and report; the verdict comes from executing the tree. This keeps the authority model
intact: the model proposes the thing under test, deterministic code decides what happened to it.

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

Choose Option A for this sprint: keep `sqlite-credit-v1` as the single supported CrashCheck slice.
A second adapter would not close the missing live transport, exact sponsor receipt, public hosting,
or demo-video gates, and would add a new trust surface before a second consumer is justified.

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

Only the original `idempotency-retry` verifier is connected to Nemotron and ConTree. Its JUnit XML is
guest-produced bounded evidence, not provider-owned attestation, so arbitrary repositories remain
unsupported. CrashCheck live provider transport is explicitly unimplemented; it remains blocked
even when external credentials and image prerequisites are otherwise satisfied.

## Published low-level ConTree client

Pin `contree-client[httpx]==0.3.0`. When selected, the documented high-level SDK interface was not
available in a published `contree-sdk` build, while the official low-level client exposed the image,
operation, file, stream, and metrics receipts required by the verifier. Revisit this seam when the
published high-level interface provides equivalent evidence.
