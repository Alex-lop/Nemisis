# Proof ledger

This ledger separates observed behavior from transport and product claims. The committed evidence
was executed from clean source `ddaf186aa81b8a7ebd442da1f2dfeee6878e7dce` and published by
`3d66ccd4499fae5f1d6fbe5beee4b097d3ce3949`. Later commits changed engine bytes (the current engine
code digest is `7df54c45ce280fa4af135d35cd338d4e6d8b10f5e67d69e5b303b9ec95937361`); the committed hero stays
bound to its own exact source and engine and is not relabelled. A fresh `check` at the current
commit prints its own capsule and engine digests.

| Capability | Truth state | Exact evidence |
| --- | --- | --- |
| Real process-group kill and confirmed death | `LOCAL` / `FIXTURE` / `VALID` | Manifest attempt receipts record parent signal `9`, first-worker exit `-9`, and unchanged post-kill durable state. |
| Fresh replay of the identical event | `LOCAL` / `FIXTURE` / `VALID` | Every proof attempt has two distinct worker and IPC nonces with event digest `4ad9ce16…`. |
| Candidate-blind witness selection | `VERIFIED` | Candidate-invariance and ordering tests; two base-only receipts precede candidate materialization. |
| Exact anchor mapping | `VERIFIED` | Unique mappings bind exact tree digests; zero, multiple, and invalid (async or wrong-arity) supported mappings publish `EVIDENCE_INCOMPLETE` plus `anchor-resolution.json`, each exercised through `check`. |
| Fixture-scoped fault-action necessity | `VERIFIED` | One deletion trial; 2/2 fresh empty-schedule base worlds are `EXACTLY_ONCE`; schema-v2 field is `sole_fault_action_necessary_for_fixture`. |
| Base/candidate/corrected verdicts | `LOCAL` / `FIXTURE` / `VALID` | Five fresh valid worlds per role: buggy and misleading-green duplicate; atomic completes exactly once. |
| Repro Capsule | `VERIFIED` | Capsule `1025d9c6e014394cf80629d180e7cb4fb1a77a4b7b26934980b5f5ea975069a8`, engine digest `47d78405…`, exact event/environment/seed/tree identities. |
| Installed-wheel replay and regression | `VERIFIED` | External temp install: base/candidate/corrected replay exits `1`/`1`/`0`; exported regression fails candidate and passes atomic. In-suite: base-role replay yields `BUG_REPRODUCED`, a fixed tree under `--role base` is `EVIDENCE_INCOMPLETE`, and an over-crediting candidate is `INVARIANT_FAILED`, never proven. |
| Measured benchmark | `LOCAL` / `FIXTURE` | Result `11016ce964b88961c246c91eb1ae437cf0ff9e9547a794ad845776af52af864a`; strict schema/digest validation passes. |
| Static one-minute viewer | `LOCAL` / `FIXTURE` | Verdict-first five-beat viewer with stepped replay and a pinned `LOCAL` / `FIXTURE` bar, exact receipt bindings, fail-closed runtime, and explicit “Replay fixture evidence” control. |
| Project gates | `VERIFIED` | Locked sync, formatting, Ruff, mypy, 316 local tests, sdist, and wheel pass. |
| GitHub composite Action | `VERIFIED_WITH_BOUNDARY` | Exact-SHA CI executes `uses: ./`, expected candidate rejection, artifact validation, installed-wheel smoke, and corrected replay. The copyable workflow pins engine `f05ae921…`. Not exercised by CI: remote-action download, real upload transfer, and the action's Git-ref branch (resolving `base` to a commit SHA and reading the base-owned `.nemisis/config.json`), which every real pull request takes; that branch is covered only by the Python-level Git materialization tests. |
| Nemotron contract proposal (`init --nemotron`) | `MOCKED` / `BLOCKED` | Wired into the CLI and into the check manifest and report; injected-client tests prove candidate blindness, fail-closed rejection, secret-free receipts, and sidecar binding. No `NEBIUS_API_KEY` here, so no current-tree `LIVE` receipt. |
| Differential Nemotron + ConTree path | `IMPLEMENTED_NOT_CURRENTLY_OBSERVED` | Bounded adapter and guest-receipt tests exist, but no current-tree provider receipt exists. |
| CrashCheck ConTree transport | `BLOCKED` | Not implemented; local execution is never substituted for live. |
| Genuine current-tree live proof | `BLOCKED` | Missing Token Factory key, ConTree profile, immutable image UUID, and CrashCheck transport. |
| Browser visual/screenshot QA | `LOCAL` / `FIXTURE` | Headless Chrome (Playwright) rendered the served viewer in its initial, mid-replay, final-receipt, and fail-closed states and the generated fail/pass reports; captures are committed under `docs/assets/screenshots/` and checked by `tests/test_readme_truth.py`. |
| Hosted URL and demo video | `PARTIAL` | A 30-second `vhs` terminal recording of a real local run (`crashcheck-demo.gif`) and terminal stills are committed; no hosted URL, no narrated video, and no provider run is claimed. |
| Arbitrary repositories, databases, languages, or general schedule search | `UNSUPPORTED` | The alpha supports the audited Python 3.12/POSIX/SQLite `CreditStore` slice only. |

## Evidence axes

For the committed hero:

- transport: `LOCAL`;
- execution: `COMPLETED`;
- provenance: `FIXTURE`;
- integrity: `VALID`;
- candidate verdict: `PATCH_FAILED_STILL_REPRODUCES`; and
- corrected control: `FIX_PROVEN_FOR_THIS_CAPSULE`.

Transport success never supplies the behavioral verdict. The verdict comes from validated guest
process/state receipts and fixed rules. No fixture, mock, historical result, or provider-looking ID
is represented as `LIVE` or `RECORDED_LIVE`.

## Review links

- [measured benchmark](../benchmarks/results/crashcheck-v1.json)
- [viewer](assets/crashcheck-hero/index.html)
- [run manifest](assets/crashcheck-hero/runs/local-20260831T020037-73e97ef2/manifest.json)
- [full receipt](assets/crashcheck-hero/runs/local-20260831T020037-73e97ef2/report.html)
- [capsule](assets/crashcheck-hero/repros/double-credit/1025d9c6e014394cf80629d180e7cb4fb1a77a4b7b26934980b5f5ea975069a8/capsule.json)
- [live prerequisites](LIVE_RUNBOOK.md)
- [turnkey live setup](LIVE_SETUP.md)
- [screenshots and recording](assets/screenshots/)
