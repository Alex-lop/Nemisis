# Proof ledger

This ledger separates observed behavior from transport and product claims. The committed evidence
was executed from clean source `0b29f3381ce3c8188cef521de7726d0b02af55b3` on 2026-09-05 and
published by the commit that follows it on `overnight/hardening`. It was recorded at the current engine
code digest is `a9b1227d5c32db9500232be0a161906a23128f7c95d5d9e06c82a26bc34897ad`, so
`tests/test_static_hero.py` re-validates every committed receipt against the live strict models. A
fresh `check` at any later engine prints its own capsule and engine digests and is never relabelled.

| Capability | Truth state | Exact evidence |
| --- | --- | --- |
| Real process-group kill and confirmed death | `LOCAL` / `FIXTURE` / `VALID` | Manifest attempt receipts record parent signal `9`, first-worker exit `-9`, and unchanged post-kill durable state. |
| Fresh replay of the identical event | `LOCAL` / `FIXTURE` / `VALID` | Every proof attempt has two distinct worker and IPC nonces with event digest `4ad9ce16…`. |
| Candidate-blind witness selection | `VERIFIED` | Candidate-invariance and ordering tests; two base-only receipts precede candidate materialization. |
| Exact anchor mapping | `VERIFIED` | Unique mappings bind exact tree digests; zero, multiple, and invalid (async or wrong-arity) supported mappings publish `EVIDENCE_INCOMPLETE` plus `anchor-resolution.json`, each exercised through `check`. |
| No-crash control (the base's duplicate needs the crash) | `VERIFIED` | 2/2 fresh no-kill base deliveries are `EXACTLY_ONCE`; the receipt still carries the older field name `sole_fault_action_necessary_for_fixture`. |
| Base/candidate/corrected verdicts | `LOCAL` / `FIXTURE` / `VALID` | Five fresh valid worlds per role: buggy and misleading-green duplicate; atomic completes exactly once, and its commit sweep (census `credit_and_mark`, one kill point) ends exactly once. |
| Repro Capsule | `VERIFIED` | Capsule `6b51d8f0cb06a2892cac90de36d81a378f3ea8c63d40920aec3f8b72f602c18d`, engine digest `a9b1227d…`, exact event/environment/seed/tree identities. |
| Installed-wheel replay and regression | `VERIFIED` | External temp install: base/candidate/corrected replay exits `1`/`1`/`0`; exported regression fails candidate and passes atomic. In-suite: base-role replay yields `BUG_REPRODUCED`, a fixed tree under `--role base` is `EVIDENCE_INCOMPLETE`, and an over-crediting candidate is `INVARIANT_FAILED`, never proven. |
| Measured benchmark | `LOCAL` / `FIXTURE` | Result `9b455bdee94234178b158d513a033924996dca4a6213b1513aa61acdca480973`; strict schema/digest validation passes. |
| Static one-minute viewer | `LOCAL` / `FIXTURE` | Verdict-first five-beat viewer with stepped replay and a pinned `LOCAL` / `FIXTURE` bar, exact receipt bindings, fail-closed runtime, and explicit “Replay fixture evidence” control. |
| Project gates | `VERIFIED` | Locked sync, formatting, Ruff, mypy, 348 local tests, sdist, and wheel pass. |
| GitHub composite Action | `VERIFIED_WITH_BOUNDARY` | Exact-SHA CI executes `uses: ./`, expected candidate rejection, artifact validation, installed-wheel smoke, and corrected replay. The copyable workflow pins engine `f05ae921…`. Not exercised by CI: remote-action download, real upload transfer, and the action's Git-ref branch (resolving `base` to a commit SHA and reading the base-owned `.nemisis/config.json`), which every real pull request takes; that branch is covered only by the Python-level Git materialization tests. |
| Nemotron as coding agent (`propose-patch`) | `MOCKED` / `BLOCKED` | Wired into the CLI, the candidate tree (`.nemisis/agent-patch.json`), the check manifest, and the report; injected-client tests prove the prompt is checker-blind, unsafe modules write nothing, a model-written fix is proven, and a model-written mark-first patch fails the commit sweep. No `NEBIUS_API_KEY` here, so no `LIVE` authorship receipt. |
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
- [run manifest](assets/crashcheck-hero/runs/local-20260905T074340-46797375/manifest.json)
- [full receipt](assets/crashcheck-hero/runs/local-20260905T074340-46797375/report.html)
- [capsule](assets/crashcheck-hero/repros/double-credit/6b51d8f0cb06a2892cac90de36d81a378f3ea8c63d40920aec3f8b72f602c18d/capsule.json)
- [live prerequisites](LIVE_RUNBOOK.md)
- [turnkey live setup](LIVE_SETUP.md)
- [screenshots and recording](assets/screenshots/)
