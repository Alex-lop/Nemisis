# Proof ledger

This ledger separates observed behavior from transport and product claims. The committed evidence
was executed from clean source `14cd428bc01d4da44bf05758afb1cb69188479f5` on 2026-09-06 at engine
`39833a5640c9053727c7832d6b72ddb14b4684d21b04daa6043c4e32c182e53b` and published by the commit
that follows it on `overnight2/docs-and-evidence`. Later commits may change engine bytes (the current engine
code digest is `228430389fa7292570b4df0772ed0fdb9ee915a6e89fe49b7dcf9aa3ac588831`); when they do,
`tests/test_static_hero.py` checks the committed receipts structurally rather than against the live
strict models, and the hero stays bound to its own engine. A fresh `check` at any later engine
prints its own capsule and engine digests and is never relabelled.

| Capability | Truth state | Exact evidence |
| --- | --- | --- |
| Real process-group kill and confirmed death | `LOCAL` / `FIXTURE` / `VALID` | Manifest attempt receipts record parent signal `9`, first-worker exit `-9`, and unchanged post-kill durable state. |
| Fresh replay of the identical event | `LOCAL` / `FIXTURE` / `VALID` | Every proof attempt has two distinct worker and IPC nonces with event digest `4ad9ce16…`. |
| Candidate-blind witness selection | `VERIFIED` | Candidate-invariance and ordering tests; two base-only receipts precede candidate materialization. |
| Exact anchor mapping | `VERIFIED` | Unique mappings bind exact tree digests; zero, multiple, and invalid (async or wrong-arity) supported mappings publish `EVIDENCE_INCOMPLETE` plus `anchor-resolution.json`, each exercised through `check`. |
| No-crash control (the base's duplicate needs the crash) | `VERIFIED` | 2/2 fresh no-kill base deliveries are `EXACTLY_ONCE`, recorded on the receipt's `sole_fault_action_necessary_for_fixture` flag. |
| Base/candidate/corrected verdicts | `LOCAL` / `FIXTURE` / `VALID` | Five fresh valid worlds per role: buggy and misleading-green duplicate; atomic completes exactly once, and its commit sweep (census `credit_and_mark`, one kill point) ends exactly once. |
| Repro Capsule | `VERIFIED` | Capsule `800b4651c63b4f4a091d6366d84bcea65931f52da872e3068fd1bc4ef7db4572`, engine digest `39833a56…`, exact event/environment/seed/tree identities. |
| Installed-wheel replay and regression | `VERIFIED` | CI installs the built wheel outside the checkout and drives `verify`, a `check` asserted to exit `1`, and one corrected `replay` from it; no committed receipt covers a base/candidate/corrected replay triple from an install. In-suite: the exported regression runs from a clean directory, failing the candidate (exit `1`) and passing atomic (exit `0`); base-role replay yields `BUG_REPRODUCED`, a fixed tree under `--role base` is `EVIDENCE_INCOMPLETE`, and an over-crediting candidate is `INVARIANT_FAILED`, never proven. |
| Measured benchmark | `LOCAL` / `FIXTURE` | Result `b7a03b92f4bb8cf1a6416b1e88a4ff26d62f74d5fd172607d800c8aab7b96643`; strict schema/digest validation passes. |
| Static one-minute viewer | `LOCAL` / `FIXTURE` | Verdict-first five-beat viewer with stepped replay and a pinned `LOCAL` / `FIXTURE` bar, exact receipt bindings, fail-closed runtime, and explicit “Replay fixture evidence” control. |
| Project gates | `VERIFIED` | Locked sync, formatting, Ruff, mypy, 482 local tests, sdist, and wheel pass. |
| GitHub composite Action | `VERIFIED_WITH_BOUNDARY` | Exact-SHA CI executes `uses: ./`, expected candidate rejection, artifact validation, installed-wheel smoke, and corrected replay. The copyable workflow pins the reviewed action commit named in [STATUS.md](STATUS.md) (`4db42137…`). Not exercised by CI: remote-action download, real upload transfer, and the action's Git-ref branch (resolving `base` to a commit SHA and reading the base-owned `.nemisis/config.json`), which every real pull request takes; that branch is covered only by the Python-level Git materialization tests. |
| Nemotron as coding agent (`propose-patch`) | `MOCKED` / `BLOCKED` | Wired into the CLI, the operator-side receipt (`.nemisis/agent-patches/`), the check manifest, and the report; injected-client tests prove the prompt is checker-blind, unsafe modules write nothing, a model-written fix is proven, and a model-written mark-first patch fails the commit sweep. No `NEBIUS_API_KEY` here, so no `LIVE` authorship receipt. |
| Commit sweep and red-team zoo | `LOCAL` / `FIXTURE` / `VERIFIED` | A claimed fix whose five boundary worlds all end exactly once is then killed once after each commit its first delivery makes, up to 64; three red-team handlers that fooled or nearly fooled the earlier engine are packaged as `fixture:sqlite-credit-v1/{mark-first,leftover-credit,never-marks}` with pinned verdicts; `fixture:sqlite-credit-v1/raw-sql` (the fix as one raw SQL transaction) is pinned to `EVIDENCE_INCOMPLETE` with the store-call remedy in its summary; `fixture:sqlite-credit-v1/shadow-table` (dedup state in a table inside the store's database, a 2026-09-06 false pass) is pinned to `EVIDENCE_INCOMPLETE` / `INVALID`, with fifteen sibling shapes (three header fields, a rowid, the free-page count, files and directories beside, above, under `HOME` and `TMPDIR`, in the bound tree and deleted on exit, the file's mode bits, a re-pointed ledger row, a renamed table, a split schedule) pinned in `tests/test_verdict_paths.py`. |
| Nemotron contract proposal (`init --nemotron`) | `MOCKED` / `BLOCKED` | Wired into the CLI and into the check manifest and report; injected-client tests prove candidate blindness, fail-closed rejection, secret-free receipts, and sidecar binding. No `NEBIUS_API_KEY` here, so no current-tree `LIVE` receipt. |
| Differential Nemotron + ConTree path | `IMPLEMENTED_NOT_CURRENTLY_OBSERVED` | Bounded adapter and guest-receipt tests exist, but no current-tree provider receipt exists. |
| CrashCheck ConTree transport | `BLOCKED` | Not implemented; local execution is never substituted for live. |
| Genuine current-tree live proof | `BLOCKED` | Missing Token Factory key, ConTree profile, immutable image UUID, and CrashCheck transport. |
| Browser visual/screenshot QA | `LOCAL` / `FIXTURE` | Headless Chrome (Playwright) rendered the served viewer in its initial, mid-replay, final-receipt, and fail-closed states and the generated fail/pass reports; captures are committed under `docs/assets/screenshots/` and checked by `tests/test_readme_truth.py`. |
| Hosted URL and demo video | `PARTIAL` | A 30-second `vhs` terminal recording of a real local run (`crashcheck-demo.gif`) and terminal stills are committed; no hosted URL, no narrated video, and no provider run is claimed. |
| Adversarial generator (`nemisis redteam`) | `LOCAL` / `VERIFIED` | A grammar over store operations and the writes around the store that hostile reviews wrote by hand (files beside, above, under `HOME` and `TMPDIR`, a file tidied away, a raw SQL effect, a table, a pragma, a re-pointed row, a swallowed second marker, a retry loop, a helper function, a world-detection attempt) renders handlers in either scenario's vocabulary; an oracle computed from the operation sequence alone, which knows when the kernel probes and when it scans, names the verdict each must earn; `tests/test_redteam.py` pins the oracle on the whole zoo and on forty-five shapes, runs ten fixed-seed credit handlers and four inventory shapes with zero disagreements; `.github/workflows/nightly.yml` runs three hundred per scenario, and its first GitHub run ([34086693284](https://github.com/Alex-lop/Nemisis/actions/runs/34086693284)) had zero disagreements. The generator is not an engine resource. |
| Second scenario (`sqlite-inventory-v1`) | `LOCAL` / `FIXTURE` / `VERIFIED` | Own seed (stock 10), own effect direction (a decrement), own predicate; buggy replays to `BUG_REPRODUCED`, misleading-green to `PATCH_FAILED_STILL_REPRODUCES` (6 units), atomic to `FIX_PROVEN_FOR_THIS_CAPSULE` (8 units), mark-first to `PATCH_FAILED_INVARIANT_BROKEN` (10 units, marked); `tests/test_inventory_scenario.py`, and CI smokes it from the wheel. |
| Arbitrary repositories, databases, languages, or general schedule search | `UNSUPPORTED` | The alpha supports the two audited Python 3.12/POSIX/SQLite scenarios (`CreditStore`, `InventoryStore`) only. |

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
- [run manifest](assets/crashcheck-hero/runs/local-20260906T155348-0b0883b5/manifest.json)
- [full receipt](assets/crashcheck-hero/runs/local-20260906T155348-0b0883b5/report.html)
- [capsule](assets/crashcheck-hero/repros/double-credit/800b4651c63b4f4a091d6366d84bcea65931f52da872e3068fd1bc4ef7db4572/capsule.json)
- [live prerequisites](LIVE_RUNBOOK.md)
- [turnkey live setup](LIVE_SETUP.md)
- [screenshots and recording](assets/screenshots/)
