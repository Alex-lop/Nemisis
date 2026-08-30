# Decisions

## Global Token Factory endpoint and Nemotron 3 Super

Use `https://api.tokenfactory.nebius.com/v1/` because current Token Factory guidance recommends
the global endpoint over region-specific public URLs. Default to
`nvidia/nemotron-3-super-120b-a12b` because its current official model documentation explicitly
lists structured output. Runtime catalog validation remains authoritative; no automatic model
fallback exists.

## Published low-level ConTree client

Pin `contree-client[httpx]==0.3.0`. On 2026-08-30 the current high-level SDK documentation used an
injected-client API that no published `contree-sdk` build exposed. The official low-level client
is published and exposes the operation UUIDs required by evidence receipts. Revisit this when the
documented high-level API ships.

## One immutable bundle, external to candidate tests

Snapshot regression tests from the base fixture and combine them with generated tests and the
trusted runner. Candidate tests/configuration remain in the source world but are not selected.
The live runner checks its uploaded archive digest and rejects any bundle mutation observed during
execution.

The first live slice deliberately accepts only the immutable packaged source/candidate and a
small AST-constrained generated-test subset, with Sandbox networking disabled. ConTree client
0.3.0 returns guest-written stdout/files rather than a provider-owned test-result channel; do not
extend live verification to arbitrary repositories until that trust boundary is replaced.

## No repair or FastAPI yet

Milestones 4–5 are conditional on a genuine current-tree inference and Sandbox run. Credentials
and a prepared root image are unavailable here, so expanding into repair or a web application
would not strengthen the unverified live assumption.
