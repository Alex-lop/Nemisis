# Status

Updated 2026-09-05 (America/New_York). Hackathon deadline: 2026-10-30 10:00 PDT.

## Exact identities

Committed hero evidence (regenerated 2026-09-06 at engine `14cd428`):

- measured clean source: `14cd428bc01d4da44bf05758afb1cb69188479f5`
- evidence/viewer publication: the commit that follows it on `overnight2/docs-and-evidence`
- engine code digest at that source: `39833a5640c9053727c7832d6b72ddb14b4684d21b04daa6043c4e32c182e53b`
- capsule digest: `800b4651c63b4f4a091d6366d84bcea65931f52da872e3068fd1bc4ef7db4572`
- benchmark result digest: `b7a03b92f4bb8cf1a6416b1e88a4ff26d62f74d5fd172607d800c8aab7b96643`
- the capsule and benchmark digests are bound to CPython 3.12.13 / SQLite 3.53.1 / Darwin arm64
  through the runner environment digest; only the engine code digest is environment-independent

Current tree:

- engine code digest: `2647b09453078364c29c86d1c0c6ec9b880a99e06999a6d3b619286b2e2991c8`
  (`tests/test_docs_identity.py` pins this value, so it cannot rot; when it differs from the hero's
  engine above, `tests/test_static_hero.py` checks the committed receipts structurally and the hero
  is not relabelled)
- interpreter pinned by `.python-version` to 3.12, matching CI and the measured evidence
- reviewed action pin: `4db42137ce137b53a8239403a8b0c3e17a24489d`, the exact `main` commit that
  [`.github/examples/crashcheck.yml`](../.github/examples/crashcheck.yml) runs
  (`tests/test_docs_identity.py` fails when the two differ; bump both together after merging
  engine changes, or anyone who copies the example gets an older engine)

## Product state

CrashCheck's supported Python/SQLite alpha is locally demonstrated:

- the misleading-green candidate passes its existing test and an ordinary sequential duplicate;
- a parent-owned process group reaches the durable `$25` effect, receives `SIGKILL`, and confirms
  exit `-9`;
- a fresh worker with a distinct nonce/session replays the byte-identical event;
- 5/5 candidate worlds end at `$50`, two effects, and one marker;
- 5/5 atomic worlds end at `$25`, one effect, and one marker; and
- the exported capsule/regression fails on misleading-green and passes on atomic from a clean
  directory outside the checkout; CI runs `check` (exit `1`) and `replay` from the built wheel in a
  temporary directory outside the workspace.

New since 2026-09-05, from `overnight/hardening` and the `overnight2/*` branches that followed it:

- The checker was red-teamed by hand, then by the generator below. Two false passes were found and
  fixed: a handler that marks first and credits second (lost credit) and a handler that writes the
  credit around the store (invisible kill window). A claimed fix that survives the capsule's own
  kill point is then killed once after each of its reported store commits (`CommitSweepReceipt`),
  and every durable change must be attributable to a reported store commit.
- Complete-but-wrong candidates are failed patches, not missing evidence:
  `PATCH_FAILED_INVARIANT_BROKEN` (exit `1`) joins the verdict table; receipts validate through one
  shared final-state rule so real evidence is never rejected as an "orchestration ValidationError".
- `nemisis propose-patch`: Nemotron plays the coding agent, checker-blind; its module is shape
  checked, becomes an ordinary candidate, and is named as the author in the report. `MOCKED` in
  tests; `LIVE` needs `NEBIUS_API_KEY`, absent here.
- `nemisis redteam` generates handlers from a grammar over store operations and the writes
  around the store that two hostile reviews wrote by hand (a table, a pragma, files beside, above,
  under `HOME` and `TMPDIR`, a file tidied away before returning, a re-pointed row, a swallowed
  second marker, a retry loop, a helper function, a world-detection attempt) and compares every
  verdict with an oracle, in either scenario's vocabulary; ten cases run in the normal suite,
  three hundred per scenario nightly. The nightly's first GitHub run is
  [34086693284](https://github.com/Alex-lop/Nemisis/actions/runs/34086693284) (300 handlers, seed
  20260907, 0 disagreements, on the engine before this grammar).
- Attribution reads the whole database file (schema, every durable header field a commit never
  changes, every row with its rowid) and the whole per-world directory (cwd, its two parents,
  `HOME`, `TMPDIR`, the bound tree entry by entry) after the kill, between the census deliveries,
  and at the end, after two hostile reviews on 2026-09-06 found eleven handlers that earned
  `FIX_PROVEN_FOR_THIS_CAPSULE` through hidden flags (a table, three header fields, a rowid, the
  free-page count, a re-pointed row, a renamed table, files and directories beside, above, under
  `~`, under `TMPDIR`, in the bound tree, deleted on exit). Each is pinned in
  `tests/test_verdict_paths.py`; the table one ships as `fixture:sqlite-credit-v1/shadow-table`.
  Two channels stay outside local mode's sight and are named in `docs/SECURITY.md`.
- Three red-team handlers ship as `fixture:sqlite-credit-v1/{mark-first,leftover-credit,never-marks}`,
  and `fixture:sqlite-credit-v1/raw-sql` is the textbook fix written as one raw SQL transaction:
  it gets no verdict and a one-line remedy, because a write the store did not make has no kill
  point (exit `2`, summary and report name `store.credit_and_mark(...)`).
- Worker output is drained (chatty handlers no longer time out), the worker runs outside the bound
  tree (relative file writes no longer dirty it), cleanup errors no longer mask primary failures,
  and split worlds are named ("3 DUPLICATE_EFFECT, 2 EXACTLY_ONCE") instead of averaged.
- The "single-action necessity proof" is called what it is, a no-crash control.
- The judge's first five minutes: `init` refuses a target the base tree cannot bind at draft
  time, in the sentence `check` would have printed plus the one change that makes it bind;
  every anchor refusal, the no-crash control, the corrected control, and the eighteen ways five
  worlds can fail to cohere name what happened and, where one exists, the remedy; `nemisis
  --version` exists and `redteam` says what to do about an existing `--out`.

New since 2026-08-30: `nemisis init --nemotron` asks Nemotron on Token Factory for a candidate-blind
contract proposal (audited catalog IDs plus the expected single effect), accepts it only when fixed
rules agree, writes a secret-free receipt to `.nemisis/proposal.json`, and `check` carries that
receipt into the manifest and report. The model never sees a candidate and never touches the verdict.

The committed one-minute viewer is served with:

```bash
uv run python -m http.server 8000 --bind 127.0.0.1
```

Then open <http://127.0.0.1:8000/docs/assets/crashcheck-hero/>. It remains hidden until the committed
benchmark and manifest pass their runtime bindings. This is `LOCAL` / `FIXTURE` evidence, not a
provider run.

## Verified gates

- locked dependency sync, formatter, Ruff, mypy, 507 tests, and package build: pass locally on
  Python 3.12.13; CI runs the same gate on CPython 3.12 and 3.13
  ([run 34011484455](https://github.com/Alex-lop/Nemisis/actions/runs/34011484455), both legs green);
- CI passed on the older commits these links were written for, every one of them earlier than the
  source measured above:
  [successful run 33348963355](https://github.com/Alex-lop/Nemisis/actions/runs/33348963355),
  [successful run 33349114096](https://github.com/Alex-lop/Nemisis/actions/runs/33349114096), and
  [successful run 33349903736](https://github.com/Alex-lop/Nemisis/actions/runs/33349903736); no CI
  run at the measured source is cited here yet;
- local doctor: `READY` for Python 3.12, POSIX `SIGKILL`, and SQLite WAL/`FULL`;
- `init --nemotron` without `NEBIUS_API_KEY`: exit `2`, nothing written (verified);
- `init --nemotron` with an injected client, then `check --scenario .nemisis/config.json`: receipt
  labelled `MOCKED` in the manifest and report, verdict unchanged (verified; this is a test path,
  not a live claim);
- adversarial review on 2026-09-03 and the resulting fixes: a config or exported contract can no
  longer stamp `LIVE`; `replay` refuses untrusted forks like `check`; the viewer command binds
  loopback; every refusal path that review named now has a test in
  `tests/test_trust_boundaries.py`.

Visual evidence now exists and is committed under `docs/assets/screenshots/`: a 30-second `vhs`
terminal recording (`crashcheck-demo.gif`: buggy reproduces, the agent's patch still reproduces, the
atomic fix is proven, all under one capsule), terminal stills of `check`, the atomic `replay`,
`doctor --mode live`, and the green test suite, and headless-Chrome screenshots of the evidence viewer
(initial, mid-replay, final receipt, fail-closed) and of the generated fail/pass reports. The recording,
stills, and reports are real local runs of the packaged fixture on this tree; the viewer captures
render the committed hero receipt, bound to its own earlier commit; every surface carries `LOCAL` /
`FIXTURE` labels where it shows labels; `tests/test_readme_truth.py` fails if an embedded image is missing or
malformed. The viewer was redesigned on 2026-09-04 (stepped replay, pinned truth-label bar,
PASS / FAIL colour language) and re-verified by the same tests. No public hosted URL is claimed and no
provider run appears in any image.

## Sponsor and submission state

`LIVE` remains `BLOCKED`, without fallback:

- `NEBIUS_API_KEY` is absent, so no current-tree Nemotron proposal receipt exists; the code path
  that would produce it is wired and contract-tested;
- no usable ConTree profile is present;
- `NEMISIS_CONTREE_ROOT_IMAGE` is absent; and
- CrashCheck's ConTree provider transport is not implemented.

The first genuine sponsor receipt is one command away once a Token Factory key exists:
`nemisis init --nemotron` at an exact commit, with `.nemisis/proposal.json` committed and its digest
named in this file. The exact turnkey sequence, with the success and failure output spelled out, is
[`docs/LIVE_SETUP.md`](LIVE_SETUP.md). Until then Nemisis is a verified local alpha with a wired but unexercised live
model path, not yet hackathon-submission-ready.

## Direction

Option A is retained: one excellent SQLite slice, made undeniable. In order:

1. Obtain a Token Factory key; capture and commit the exact-SHA `LIVE` proposal receipt.
2. Record the spoken demo from `docs/DEMO.md` (the silent 30-second terminal GIF already exists).
3. Connect the CrashCheck kernel to a Token Factory Sandbox (spawn, subprocess result, process-group
   kill) against one immutable image so untrusted pull requests can be checked; keep `doctor` and
   `check --mode live` `BLOCKED` until a real receipt exists.
4. Publish the static viewer at a public URL.

A second scenario exists: `sqlite-inventory-v1` (stock 10 to 8, oversold to 6 by the crash),
built on the `Scenario` seam that now owns every point `sqlite_runner.py` and `crash_models.py`
used to hardcode. A second storage backend is still deferred by design.
