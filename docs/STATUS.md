# Status

Updated 2026-09-05 (America/New_York). Hackathon deadline: 2026-10-30 10:00 PDT.

## Exact identities

Committed hero evidence (regenerated 2026-09-05 at the current engine):

- measured clean source: `0b29f3381ce3c8188cef521de7726d0b02af55b3`
- evidence/viewer publication: the commit that follows it on `overnight/hardening`
- engine code digest at that source: `a9b1227d5c32db9500232be0a161906a23128f7c95d5d9e06c82a26bc34897ad`
- capsule digest: `6b51d8f0cb06a2892cac90de36d81a378f3ea8c63d40920aec3f8b72f602c18d`
- benchmark result digest: `9b455bdee94234178b158d513a033924996dca4a6213b1513aa61acdca480973`
- the capsule and benchmark digests are bound to CPython 3.12.13 / SQLite 3.53.1 / Darwin arm64
  through the runner environment digest; only the engine code digest is environment-independent

Current tree:

- engine code digest: `a9b1227d5c32db9500232be0a161906a23128f7c95d5d9e06c82a26bc34897ad`
  (the same engine that recorded the committed hero; `tests/test_docs_identity.py` pins this value,
  so it cannot rot)
- interpreter pinned by `.python-version` to 3.12, matching CI and the measured evidence

## Product state

CrashCheck's supported Python/SQLite alpha is locally demonstrated:

- the misleading-green candidate passes its existing test and an ordinary sequential duplicate;
- a parent-owned process group reaches the durable `$25` effect, receives `SIGKILL`, and confirms
  exit `-9`;
- a fresh worker with a distinct nonce/session replays the byte-identical event;
- 5/5 candidate worlds end at `$50`, two effects, and one marker;
- 5/5 atomic worlds end at `$25`, one effect, and one marker; and
- the exported capsule/regression fails on misleading-green and passes on atomic from an installed
  wheel outside the checkout.

New since 2026-09-05 (overnight hardening, branch `overnight/hardening`):

- The checker was red-teamed with thirty adversarial handlers. Two false passes were found and
  fixed: a handler that marks first and credits second (lost credit) and a handler that writes the
  credit around the store (invisible kill window). Every claimed fix is now killed once after each
  of its store commits (`CommitSweepReceipt`), and every durable change must be attributable to a
  reported store commit.
- Complete-but-wrong candidates are failed patches, not missing evidence:
  `PATCH_FAILED_INVARIANT_BROKEN` (exit `1`) joins the verdict table; receipts validate through one
  shared final-state rule so real evidence is never rejected as an "orchestration ValidationError".
- `nemisis propose-patch`: Nemotron plays the coding agent, checker-blind; its module is shape
  checked, becomes an ordinary candidate, and is named as the author in the report. `MOCKED` in
  tests; `LIVE` needs `NEBIUS_API_KEY`, absent here.
- Three red-team handlers ship as `fixture:sqlite-credit-v1/{mark-first,leftover-credit,never-marks}`.
- Worker output is drained (chatty handlers no longer time out), the worker runs outside the bound
  tree (relative file writes no longer dirty it), cleanup errors no longer mask primary failures,
  and split worlds are named ("3 DUPLICATE_EFFECT, 2 EXACTLY_ONCE") instead of averaged.
- The "single-action necessity proof" is called what it is, a no-crash control.

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

- locked dependency sync, formatter, Ruff, mypy, 348 tests, and package build: pass locally on
  Python 3.12.13 (the suite also passed on 3.13 during development);
- exact engine CI for the committed hero: [successful run 33348963355](https://github.com/Alex-lop/Nemisis/actions/runs/33348963355);
- exact measured-source CI: [successful run 33349114096](https://github.com/Alex-lop/Nemisis/actions/runs/33349114096);
- evidence/viewer CI: [successful run 33349903736](https://github.com/Alex-lop/Nemisis/actions/runs/33349903736);
- local doctor: `READY` for Python 3.12, POSIX `SIGKILL`, and SQLite WAL/`FULL`;
- `init --nemotron` without `NEBIUS_API_KEY`: exit `2`, nothing written (verified);
- `init --nemotron` with an injected client, then `check --scenario .nemisis/config.json`: receipt
  labelled `MOCKED` in the manifest and report, verdict unchanged (verified; this is a test path,
  not a live claim);
- adversarial review on 2026-09-03 (seven lenses, two verifiers each) and the resulting fixes: a
  config or exported contract can no longer stamp `LIVE`; `replay` refuses untrusted forks like
  `check`; the viewer command binds loopback; every documented refusal path now has a test.

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

A second scenario or backend is still deferred. The overnight work chose depth over width: the
kernel now proves a patch survives every kill point of its own, not only the base's, and thirty
adversarial handlers were run against it. The seam a second scenario needs (schema, store class,
seed, probe, and final-state rule are the hardcoded points in `sqlite_credit.py` and
`crash_models.py`) is listed in `MORNING.md`.
