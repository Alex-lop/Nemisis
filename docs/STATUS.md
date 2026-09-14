# Status

Updated 2026-09-14 (America/New_York). Hackathon deadline: 2026-10-30 10:00 PDT.

## Exact identities

Committed hero evidence (regenerated 2026-09-07 at engine `c339aa9`, the third hostile round's fix):

- measured clean source: `c339aa90f32ec0874b03d51ff8432505596694b2`
- evidence/viewer publication: the commit that follows it on `overnight3/morning`
- engine code digest at that source: `29205c5be25169f0ec17faccddd824e2b931ef0efbcaadae23b6f38c7217e94d`
- capsule digest: `190d62ea98c2884eaeb6f8f30f38bdf0c733e40d186b8cfab8896a691696c0f6`
- benchmark result digest: `7d0672e42f30a30ee7a8cba2c52970e7fffbc9e154ea70b8aad21e26604d5540`
- the capsule and benchmark digests are bound to CPython 3.12.13 / SQLite 3.53.1 / Darwin arm64
  through the runner environment digest; only the engine code digest is environment-independent

Current tree:

- engine code digest: `47de6ab78521af339e43e68e00384f254c8b7cfbe18704b740a6e742f1004636`
  (`tests/test_docs_identity.py` pins this value, so it cannot rot; when it differs from the hero's
  engine above, `tests/test_static_hero.py` checks the committed receipts structurally and the hero
  is not relabelled)
- interpreter pinned by `.python-version` to 3.12, matching CI and the measured evidence
- release: `v0.2.0` is tagged at `e1aeae0` and published; the `Release` run
  [34821573278](https://github.com/Alex-lop/Nemisis/actions/runs/34821573278) went green on all
  three jobs (`build`, `github-release`, `pypi`), and `uv tool install nemisis==0.2.0` into a clean
  tool directory gave a `nemisis` whose engine code digest is the one above, whose `doctor --mode
  local` is READY, and whose verdicts on `atomic` and `tail-bytes` are `FIX_PROVEN_FOR_THIS_CAPSULE`
  and `EVIDENCE_INCOMPLETE`, the same as the checkout's
- reviewed action pin: `10dfbeecae6bba9dbde607ea8ff9e7f1b4067690`, the commit that
  [`.github/examples/crashcheck.yml`](../.github/examples/crashcheck.yml) runs (on `main` it is
  `main`'s engine; a pull request pins its own last engine commit until it merges)
  (`tests/test_docs_identity.py` fails when the two differ, and fails on `main` when
  `src/nemisis`, `action.yml`, `pyproject.toml`, or `uv.lock` at the pinned commit differs from
  `main`'s; an engine pull request carries its own bump, and
  [`pin-bump.yml`](../.github/workflows/pin-bump.yml) opens one after any engine merge that did
  not, once the repository allows Actions to open pull requests; its guard has run on every merge
  since it landed, five so far (the first:
  [34807643729](https://github.com/Alex-lop/Nemisis/actions/runs/34807643729); the engine merge:
  [34820543033](https://github.com/Alex-lop/Nemisis/actions/runs/34820543033)), each time "nothing
  to bump" because the engine pull request carried its own; it has never opened a pull request,
  because the repository setting is off)

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
  verdict with an oracle, in each registered scenario's vocabulary; ten cases run in the normal
  suite, three hundred per scenario nightly. The nightly's first GitHub run is
  [34086693284](https://github.com/Alex-lop/Nemisis/actions/runs/34086693284) (300 handlers, seed
  20260907, 0 disagreements, on the engine before this grammar); the first run at the engine that
  refuses what the nightly found is
  [34820657707](https://github.com/Alex-lop/Nemisis/actions/runs/34820657707) (300 per scenario,
  seed 34820657707, 0 disagreements, 0 unknown, with the 30 s worker budget and `--max-unknown 3`).
- Attribution reads the whole database file (schema, every durable header field a commit never
  changes, every row with its rowid) and the whole per-world directory (cwd, its two parents,
  `HOME`, `TMPDIR`, the bound tree entry by entry) after the kill, between the census deliveries,
  and at the end, after two hostile reviews on 2026-09-06 found eleven handlers that earned
  `FIX_PROVEN_FOR_THIS_CAPSULE` through hidden flags (a table, three header fields, a rowid, the
  free-page count, a re-pointed row, a renamed table, files and directories beside, above, under
  `~`, under `TMPDIR`, in the bound tree, deleted on exit). Each is pinned in
  `tests/test_verdict_paths.py`; the table one ships as `fixture:sqlite-credit-v1/shadow-table`.
  The nightly red team then caught a fourth-round shape on its own: bytes appended past the
  database's last page after the handler's last commit earned a verdict for five nights and
  `FIX_PROVEN_FOR_THIS_CAPSULE` twice, in one run (runs 34219859012, 34345065158, 34593382316, 34689225054, 34755449725; ten cases,
  twenty lines, each case in both scenarios), because SQLite's close-time checkpoint truncated
  the file before the engine's read; the engine now reads after the worker's final message and
  before it may exit, pins the main file whole during a delivery, holds the write-ahead log to
  its frames, and the shape ships as `fixture:sqlite-credit-v1/tail-bytes`; the lenses on that
  fix found and closed a flag in the header's change counter and an append to the log.
  A third review on 2026-09-07 confirmed thirty-seven more (a header field the probe never read,
  the reserved header bytes, bytes past the last page, a file flag, an extended attribute on the
  platform where the guard was inert, the mode and mtime of the world's own directories, HOME
  removed or replaced, a directory made unlistable, a scratch-tree whitelist built from names, the
  store patched at import); the probe now reads the file's raw header and length (which closed
  the orderings where the bytes outlive the worker; the ordering after the last commit waited
  for the nightly, below), the world scan
  pins every entry's metadata and refuses what it cannot list, the scratch root is known by
  recorded identity, and the worker refuses a patched store. Thirteen shapes are pinned; the
  channels that remain are listed in `docs/SECURITY.md`.
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

- the mutation ledger at this engine,
  [`docs/reports/2026-09-14-mutation-ledger.md`](reports/2026-09-14-mutation-ledger.md): 288
  mutants of the kernel's refusals, 243 killed and 45 survived on the macOS run (24 equivalent with the
  reason, 21 holes
  each naming the test it is owed); `mutants.yml` reruns the thirteen targets monthly and fails on a
  survivor the newest ledger does not list;
- locked dependency sync, formatter, Ruff, mypy, 633 tests, and package build: pass locally on
  Python 3.12.13; CI runs the same gate on CPython 3.12, 3.13, and 3.14 (the 3.14 leg first ran
  green on a real runner at
  [run 34093138705](https://github.com/Alex-lop/Nemisis/actions/runs/34093138705), where the only
  failure on all three legs was the test-count line this file requotes);
- the nightly red team's first run on GitHub's Linux:
  [run 34086693284](https://github.com/Alex-lop/Nemisis/actions/runs/34086693284), 300 generated
  handlers at seed 20260907, 0 disagreements, on the engine before tonight's grammar and fixes;
  two local sweeps of 300 per scenario at the post-fix engine also had 0 disagreements; the first
  run at the engine that refuses the tail-bytes shape, dispatched on `main` at `5b216a1`:
  [run 34820657707](https://github.com/Alex-lop/Nemisis/actions/runs/34820657707), 300 handlers
  per scenario at seed 34820657707, 0 disagreements, 0 unknown;
- a second, independent measurement of the hero on GitHub's Linux (CPython 3.12.3, SQLite 3.45.1,
  x86_64): [run 34092142968](https://github.com/Alex-lop/Nemisis/actions/runs/34092142968), the
  `Evidence` workflow at engine `228430389f…`, verdict `PATCH_FAILED_STILL_REPRODUCES`, engine and
  event digests byte-identical to the laptop's, capsule digest `85adf7b9…` and environment digest
  `13fc1958…` different, as the environment binding says they must be; its artifact is
  `linux-hero-34092142968` (90 days);
- the same check inside the `Dockerfile` image (77 MB, `python:3.12.13-slim`, SQLite 3.46.1):
  `doctor --mode local` READY and `mark-first` `PATCH_FAILED_INVARIANT_BROKEN` at the same engine
  digest, with `--network none`;
- CI passed on the older commits these links were written for:
  [run 33348963355](https://github.com/Alex-lop/Nemisis/actions/runs/33348963355),
  [run 33349114096](https://github.com/Alex-lop/Nemisis/actions/runs/33349114096),
  [run 33349903736](https://github.com/Alex-lop/Nemisis/actions/runs/33349903736), and
  [run 34011484455](https://github.com/Alex-lop/Nemisis/actions/runs/34011484455);
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
PASS / FAIL colour language) and re-verified by the same tests. The landing page and the viewer are
served at <https://alex-lop.github.io/Nemisis/> from the repository root by GitHub Pages' branch
source (the `Pages` workflow deploys only once the source is switched to GitHub Actions). No
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
4. Published: the static viewer and the landing page are live at
   <https://alex-lop.github.io/Nemisis/>.

Two more scenarios exist: `sqlite-inventory-v1` (stock 10 to 8, oversold to 6 by the crash) and
`sqlite-outbox-v1` (0 to 512 bytes on a channel, sent twice by the crash), both built on the
`Scenario` seam that now owns every point `sqlite_runner.py` and `crash_models.py` used to
hardcode; neither needed a runner change. A second storage backend is still deferred by design.
