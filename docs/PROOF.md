# Proof ledger

This ledger separates observed behavior from transport and product claims. The committed evidence
was executed from clean source `305667621ef62b49523d35a65491dafbf1e779ef` on 2026-09-05 at engine
`99ef8ade38b4616013c2d68ca9b1e8179041bf6b03aae0a58ef54928a59e1c22` and published by the commit
that follows it on `overnight/hardening`. Later commits may change engine bytes (the current engine
code digest is `99ef8ade38b4616013c2d68ca9b1e8179041bf6b03aae0a58ef54928a59e1c22`); when they do,
`tests/test_static_hero.py` checks the committed receipts structurally rather than against the live
strict models, and the hero stays bound to its own engine. A fresh `check` at any later engine
prints its own capsule and engine digests and is never relabelled.

| Capability | Truth state | Exact evidence |
| --- | --- | --- |
| Real process-group kill and confirmed death | `LOCAL` / `FIXTURE` / `VALID` | Manifest attempt receipts record parent signal `9`, first-worker exit `-9`, and unchanged post-kill durable state. |
| Fresh replay of the identical event | `LOCAL` / `FIXTURE` / `VALID` | Every proof attempt has two distinct worker and IPC nonces with event digest `4ad9ce16…`. |
| Candidate-blind witness selection | `VERIFIED` | Candidate-invariance and ordering tests; two base-only receipts precede candidate materialization. |
| Exact anchor mapping | `VERIFIED` | Unique mappings bind exact tree digests; zero, multiple, and invalid (async or wrong-arity) supported mappings publish `EVIDENCE_INCOMPLETE` plus `anchor-resolution.json`, each exercised through `check`. |
| No-crash control (the base's duplicate needs the crash) | `VERIFIED` | 2/2 fresh no-kill base deliveries are `EXACTLY_ONCE`; the receipt still carries the older field name `sole_fault_action_necessary_for_fixture`. |
| Base/candidate/corrected verdicts | `LOCAL` / `FIXTURE` / `VALID` | Five fresh valid worlds per role: buggy and misleading-green duplicate; atomic completes exactly once, and its commit sweep (census `credit_and_mark`, one kill point) ends exactly once. |
| Repro Capsule | `VERIFIED` | Capsule `41a29044bceec3314dc82d6261cc4f53e7e28a218759c09deecb97825266d99c`, engine digest `99ef8ade…`, exact event/environment/seed/tree identities. |
| Installed-wheel replay and regression | `VERIFIED` | External temp install: base/candidate/corrected replay exits `1`/`1`/`0`; exported regression fails candidate and passes atomic. In-suite: base-role replay yields `BUG_REPRODUCED`, a fixed tree under `--role base` is `EVIDENCE_INCOMPLETE`, and an over-crediting candidate is `INVARIANT_FAILED`, never proven. |
| Measured benchmark | `LOCAL` / `FIXTURE` | Result `fe98afd23f5a5bf3b5cf72a52a42558f2fb6d32ef848392fbc7f6dd26b51f8ef`; strict schema/digest validation passes. |
| Static one-minute viewer | `LOCAL` / `FIXTURE` | Verdict-first five-beat viewer with stepped replay and a pinned `LOCAL` / `FIXTURE` bar, exact receipt bindings, fail-closed runtime, and explicit “Replay fixture evidence” control. |
| Project gates | `VERIFIED` | Locked sync, formatting, Ruff, mypy, 364 local tests, sdist, and wheel pass. |
| GitHub composite Action | `VERIFIED_WITH_BOUNDARY` | Exact-SHA CI executes `uses: ./`, expected candidate rejection, artifact validation, installed-wheel smoke, and corrected replay. The copyable workflow pins engine `f05ae921…`. Not exercised by CI: remote-action download, real upload transfer, and the action's Git-ref branch (resolving `base` to a commit SHA and reading the base-owned `.nemisis/config.json`), which every real pull request takes; that branch is covered only by the Python-level Git materialization tests. |
| Nemotron as coding agent (`propose-patch`) | `MOCKED` / `BLOCKED` | Wired into the CLI, the operator-side receipt (`.nemisis/agent-patches/`), the check manifest, and the report; injected-client tests prove the prompt is checker-blind, unsafe modules write nothing, a model-written fix is proven, and a model-written mark-first patch fails the commit sweep. No `NEBIUS_API_KEY` here, so no `LIVE` authorship receipt. |
| Commit sweep and red-team zoo | `LOCAL` / `FIXTURE` / `VERIFIED` | Every claimed fix is killed once after each of its store commits; three red-team handlers that fooled or nearly fooled the earlier engine are packaged as `fixture:sqlite-credit-v1/{mark-first,leftover-credit,never-marks}` with pinned verdicts. |
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
- [run manifest](assets/crashcheck-hero/runs/local-20260905T084629-5830de69/manifest.json)
- [full receipt](assets/crashcheck-hero/runs/local-20260905T084629-5830de69/report.html)
- [capsule](assets/crashcheck-hero/repros/double-credit/41a29044bceec3314dc82d6261cc4f53e7e28a218759c09deecb97825266d99c/capsule.json)
- [live prerequisites](LIVE_RUNBOOK.md)
- [turnkey live setup](LIVE_SETUP.md)
- [screenshots and recording](assets/screenshots/)
