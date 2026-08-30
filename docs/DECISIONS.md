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
digest, and one trusted handler mapping. Zero or multiple mappings make the source unsupported.

Run output, `.git`, `.nemisis`, bytecode, and local pytest/mypy caches are excluded before source
hashing. This prevents local evidence from changing the source it claims to evaluate and avoids a
self-referential committed configuration digest.

## Candidate-blind CrashCheck ordering

CrashCheck binds the accepted issue/base contract and runs exactly two parallel, fixed, base-only
crash-boundary hypotheses before it materializes the candidate: `effect-commit-v1` and
`marker-commit-v1`. Full attempt receipts are preserved. Selection is deterministic after both are
terminal: reproduction, smaller trusted operation count, canonical rank, then digest. The selected
semantic boundary and stable minimization projection freeze the capsule; candidate content cannot
change the search, event, fault schedule, probes, parser, harness, or verdict.

The hunt does not count as proof replay. After selection, five new base worlds must reproduce before
candidate materialization; each later claimed candidate or corrected role also requires five fresh
worlds. The checked-in audited contract is `FIXTURE`; another local contract requires explicit
digest acceptance.

The bounded Nemotron contract adapter may select only audited catalog IDs and in-range scalars, but
it is not currently on the CrashCheck CLI path and no live generation is claimed.

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
