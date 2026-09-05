# Status

Updated 2026-09-04 (America/New_York). Hackathon deadline: 2026-10-30 10:00 PDT.

## Exact identities

Committed hero evidence (unchanged, bound to its own exact source and engine):

- measured clean source: `ddaf186aa81b8a7ebd442da1f2dfeee6878e7dce`
- evidence/viewer publication: `3d66ccd4499fae5f1d6fbe5beee4b097d3ce3949`
- engine code digest at that source: `47d78405ca59dee877328e16face03b15af484e3d65811e8caf213f00d8ec912`
- capsule digest: `1025d9c6e014394cf80629d180e7cb4fb1a77a4b7b26934980b5f5ea975069a8`
- benchmark result digest: `11016ce964b88961c246c91eb1ae437cf0ff9e9547a794ad845776af52af864a`
- the capsule and benchmark digests are bound to CPython 3.12.13 / SQLite 3.53.1 / Darwin arm64
  through the runner environment digest; only the engine code digest is environment-independent

Current tree:

- engine code digest: `4832df8eae3c6001cc07eaf86c737845326d6e35f5a5ac0fc8e47d17907a9aed`
  (changed by the contract-proposal and review commits; `tests/test_docs_identity.py` pins this value, so it cannot rot; a fresh `check` prints a new capsule digest bound to
  this engine, and the committed hero is not relabelled)
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

- locked dependency sync, formatter, Ruff, mypy, 312 tests, and package build: pass locally on
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

A second scenario or backend is deliberately deferred; it would add adapter surface without closing
any submission gate.
