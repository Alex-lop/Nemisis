# Product

## Product boundary

Nemisis is a deterministic evidence gate after a coding agent proposes a patch and before a human
trusts it. Natural-language intent may guide model-generated claims, but exact executions and
fixed classification rules decide what the evidence supports.

The current product has two bounded surfaces:

- `verify` is the original differential verifier. It runs an immutable trusted test bundle in exact
  base and candidate worlds and renders a claim-by-world matrix.
- CrashCheck (`init`, `check`, and `replay`) adds one deep counterexample for crash/retry safety. It
  binds a reviewed contract, kills and restarts a real worker, and exports a replayable capsule.

CrashCheck sharpens one failure mode; it does not replace the differential-verification thesis.

## Users and jobs

A developer receiving AI patches needs evidence that a promised behavior changed without breaking
protected behavior. The differential verifier answers that with `CHANGE_WITNESS` and `INVARIANT`
relations.

A backend developer facing an intermittent retry bug needs a durable counterexample stronger than
an ordinary green test. CrashCheck answers the narrower question:

> Did this exact revision defeat this frozen kill/restart/replay capsule while the observed durable
> invariants held?

## Current workflows

### Differential verification

1. Load the audited inventory ticket, base tree, candidate patch, baseline tests, and adversarial
   tests.
2. Build one immutable bundle containing tests, trusted harness, runner, parser, and digests.
3. Execute byte-identical bundle bytes in separate base and candidate worlds.
4. Parse bounded JUnit outcomes and classify each declared relation deterministically.
5. Write one JSON manifest and static HTML matrix.

Local mode uses checked-in test content and is labeled `FIXTURE`. The credentialed live path uses a
genuine Nemotron request and persistent ConTree worlds, but remains limited to this audited fixture.

### CrashCheck

1. `init` binds issue text, exact base content, target, audited catalog IDs, and an accepted contract
   digest. Non-packaged contracts require explicit acceptance.
2. `check` runs two fixed base-only crash-boundary hypotheses in parallel, deterministically selects
   the reproducing boundary, and freezes a stable semantic trace before materializing the candidate.
3. Five new worlds reconfirm the base witness; five fresh worlds then evaluate every supplied
   candidate or corrected role against the same capsule.
4. `replay` evaluates the unchanged capsule against one exact source role.
5. The run exports capsule, contract, event, hunt/engine metadata, an executable regression,
   manifest, and static HTML report.
6. The composite action projects the same CLI result into a job summary and evidence artifact.

CrashCheck records its own kill/restart/replay evidence. It does not execute or claim the ordinary
repository-test and sequential-duplicate context around the packaged example.

## Supported slices

The differential verifier supports only the packaged Python `idempotency-retry` fixture locally and
through its current live adapter. Live JUnit is bounded guest-produced evidence, so it is not yet an
arbitrary-repository verification channel.

CrashCheck supports Python 3.12 on POSIX, process groups and `SIGKILL`, SQLite through the fixed
trusted `CreditStore` adapter, `sqlite-credit-v1`, fixture refs, local directories, and exact Git
commit resolution. Local execution is for trusted checkouts. CrashCheck live execution remains
blocked until its provider transport is connected and credentials are available.

## Evidence language

`LOCAL` is an execution transport; `FIXTURE` identifies audited checked-in inputs. `LIVE` requires
genuine current-tree provider receipts. A finite matrix or capsule supports only its declared and
observed claims—it is not formal verification, vulnerability freedom, or a universal merge score.

## Success measures

- Differential base/candidate worlds use one bundle digest and produce deterministic relations.
- CrashCheck reproduces the duplicate in five fresh buggy and misleading-green worlds and observes
  exactly-once state in five fresh atomic worlds.
- Its two candidate-blind hunt worlds deterministically select one minimized semantic boundary and
  remain disjoint from every later confirmation identity.
- Every CrashCheck binding records the supplied ref, resolved commit or fixture identity, and tree
  digest; volatile run/database/worker identities remain separate.
- The exported regression fails on misleading-green and passes on atomic from an installed wheel.
- Human, JSON, HTML, and GitHub projections agree with the same underlying result.
- Live claims remain blocked unless bound to genuine current-tree receipts.

## Explicit non-goals

The alpha does not support arbitrary languages or databases, production side effects, public-PR URL
intake, safe local execution of untrusted forks, generalized chaos engineering, repair generation,
multiple model providers, a web server, PR comments, a hosted control plane, or a universal score.
