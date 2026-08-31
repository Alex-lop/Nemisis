# Status

Updated 2026-08-30 (America/New_York).

## Exact release identities

- latest execution-critical engine: `f05ae921cf3d866f69adf8415d6d7bd52071bf37`
- measured clean source: `ddaf186aa81b8a7ebd442da1f2dfeee6878e7dce`
- evidence/viewer publication: `3d66ccd4499fae5f1d6fbe5beee4b097d3ce3949`
- engine code digest: `47d78405ca59dee877328e16face03b15af484e3d65811e8caf213f00d8ec912`
- capsule digest: `1025d9c6e014394cf80629d180e7cb4fb1a77a4b7b26934980b5f5ea975069a8`
- benchmark result digest: `11016ce964b88961c246c91eb1ae437cf0ff9e9547a794ad845776af52af864a`

The evidence commit follows the measured source commit, so the benchmark and manifest correctly
retain `ddaf186…` instead of claiming the later publication commit measured itself.

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

The candidate-blind base phase runs two fixed hypotheses. It selects `effect-commit-v1` by fixed
catalog rank, then deletes that schedule's sole fault action. Two fresh empty-schedule worlds end
exactly once, so deletion is rejected and the action is necessary for this fixture witness. This
is not a general minimizer.

The committed one-minute viewer is served with:

```bash
uv run python -m http.server 8000
```

Then open <http://127.0.0.1:8000/docs/assets/crashcheck-hero/>. It remains hidden until the committed
benchmark and manifest pass their runtime bindings. This is `LOCAL` / `FIXTURE` evidence, not a
provider run.

## Verified gates

- locked dependency sync, formatter, Ruff, mypy, 267 tests, and package build: pass locally;
- exact engine CI: [successful run 33348963355](https://github.com/Alex-lop/Nemisis/actions/runs/33348963355);
- exact measured-source CI: [successful run 33349114096](https://github.com/Alex-lop/Nemisis/actions/runs/33349114096);
- evidence/viewer CI: [successful run 33349903736](https://github.com/Alex-lop/Nemisis/actions/runs/33349903736), including 267 tests, build, composite Action, and installed-wheel replay;
- local doctor: `READY` for Python 3.12, POSIX `SIGKILL`, and SQLite WAL/`FULL`;
- clean installed-wheel `init` → digest acceptance → `check`: expected candidate exit `1`;
- installed-wheel base/candidate/corrected replay: exits `1` / `1` / `0`;
- clean exported regression: fails candidate and passes corrected;
- benchmark schema/digests, viewer evidence bindings, JavaScript syntax, local links, HTTP asset
  paths, and secret/path scans: pass.

No in-app browser was available for screenshot/visual interaction QA. No public hosted URL or demo
video is claimed.

## Sponsor and submission state

`LIVE` remains `BLOCKED`, without fallback:

- `NEBIUS_API_KEY` is absent;
- no usable ConTree profile is present;
- `NEMISIS_CONTREE_ROOT_IMAGE` is absent; and
- CrashCheck's ConTree provider transport is not implemented.

The inherited differential verifier has contract-tested Nemotron/ConTree adapters, but there is no
current-tree model call, Sandbox operation, or sanitized live receipt. Nemisis is therefore a
verified local alpha, not yet hackathon-submission-ready under the directive's live-sponsor gate.

## Direction

Option A is retained: one excellent SQLite slice. A second scenario would add adapter work without
closing the higher-value live transport, public hosting, or demo-video gaps. The next milestone is
one exact-SHA CrashCheck Nemotron + ConTree receipt using an immutable image, followed by a public
viewer build and sub-three-minute recording.
