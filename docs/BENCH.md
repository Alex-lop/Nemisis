# CrashBench — design

CrashBench measures one thing: given a repository with a retry bug and a model acting as the coding
agent, does the model reach `FIX_PROVEN_FOR_THIS_CAPSULE`, and at what cost? It is the agent-surface
product turned into a benchmark. It does not exist yet as data; this document is its design, and its
first rows are `BLOCKED` on one credential export.

## What a row is

One row is one **scenario × model × exact engine**, with a `LIVE` receipt, or it is not a row.

| field | source |
| --- | --- |
| scenario | one of the audited scenarios (`sqlite-credit-v1`, …) |
| model | the exact Token Factory catalog id, recorded in the receipt, never a tier nickname |
| engine code digest | `engine_code_digest()` at the commit the row ran on |
| verdict | the final `check` verdict the agent reached |
| turns / tool calls | from the agent transcript |
| tokens in / out | from the Token Factory API response's usage at run time (the committed receipt does not carry token counts today; recording them is part of building the harness) |
| cost | tokens × the tier's published price |
| receipt | the capsule digest and the run directory; without it there is no row |

The rule is the repository's rule: **no leaderboard without receipts.** A model that did not reach a
verdict, or a run with no `LIVE` receipt, is an empty cell, not a zero and not an estimate. Truth
labels are checked by code; a `MOCKED` or `BLOCKED` run never enters the table.

## The harness

A `workflow_dispatch` GitHub workflow (the pattern of `nightly.yml` and `mutants.yml`): a matrix over
scenario × model, each job installing the wheel, driving the scripted agent loop (`list_scenarios →
port_template → map → check`, the deterministic client the MCP end-to-end test already uses, with the
model as the fixer via `propose_patch`), and uploading the transcript and the receipt. The Token
Factory key is a repository secret, read only by the job, never printed, never committed. The
alternative runner is a **Nebius Serverless Job**: the same container image and command, submitted as
a job with the key injected by the platform, so a long sweep does not hold a GitHub runner; its
result JSON is fetched and its receipts committed the same way. Either runner produces the same row
shape; the receipt, not the runner, is what the row rests on.

## Cost per row (estimated, not measured)

One `propose_patch` call sends the issue text and the base handler (a few kilobytes) and receives one
handler module (a few hundred tokens); a full agent run is a handful of such calls plus the local
`check` iterations, which cost nothing. So a row is dominated by a few thousand input tokens and a
few hundred output tokens per model turn, times a handful of turns — order 10^4 tokens per row. At
that size the tier choice is the cost, not the token count:

| tier | role | exact id | cost per row |
| --- | --- | --- | --- |
| Nemotron Nano | `draft_contract` / cheap first attempts | from the Token Factory listing | lowest |
| Nemotron Super | `propose_patch` default (`nvidia/nemotron-3-super-120b-a12b`) | packaged default | middle |
| Nemotron Ultra | the hard cases, selectable per call | from the Token Factory listing | highest |

The exact ids for Nano and Ultra come from the Token Factory catalog listing when the key is present;
this document does not guess them, and the harness records whatever id the receipt carries.

## The first three rows

Named, not run: **Nemotron Nano**, **Nemotron Super**, **Nemotron Ultra**, each on
`sqlite-credit-v1` at the current engine. They are `BLOCKED` on one export:

```
BLOCKED: printenv NEBIUS_API_KEY | wc -c → 0
```

With the key exported, the harness runs the first row and commits its receipt; without it, the table
stays empty and says so. There is no partial credit and no estimated row in the table itself — the
estimates above live only in this design.
