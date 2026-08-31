# Nemisis

> Don't ask whether the coding agent says it is done. Make the exact patch prove each claim.

Nemisis runs the patch instead of reading it. Two surfaces ship in this tree, and neither claims
universal patch safety:

- **CrashCheck** — the narrow crash/retry product. It kills a real worker after a durable side
  effect, starts a fresh worker, replays the identical event, and determines whether the exact
  patch stopped the duplicate effect. The verdict comes from durable state and process receipts,
  not model confidence.
- **The differential verifier** — the broader foundation CrashCheck is built on. One identical test
  bundle is run against a base snapshot and a candidate snapshot in separate throwaway directories,
  and each claim gets a verdict from the pair of outcomes.

Neither surface pushes, merges, comments, opens a pull request, or rewrites your git history.
Execution happens in temporary directories. The only things written under the directory you run
from are a run directory (`.nemisis/runs/`, or wherever `--output-dir` points), the immutable repro
assets beside it, and — only if you ask for it with `init` — a `.nemisis/config.json`. Both surfaces
print a decision instead of taking one.

**Scope today, before you install anything.** The engine runs two packaged fixtures:
`idempotency-retry` for the differential verifier and `sqlite-credit-v1` for CrashCheck. CrashCheck
also accepts a trusted repository through exactly one audited adapter — the fixed
`sqlite-credit-v1` scenario and its two-argument `CreditStore` contract — and nothing else. This
alpha does not analyze arbitrary handlers, databases, or languages. No live provider call has ever
been made from this repository. The full list is under "What it does not do".

## Install and run

Python 3.12+ and [uv](https://docs.astral.sh/uv/). Clone this repository, then from its root:

```bash
uv sync --frozen --dev
uv run nemisis verify --fixture idempotency-retry --mode local
```

Output observed 2026-08-31 UTC from this commit's tree (run id, bundle digest, and absolute paths
elided; the run performs real `pytest` subprocesses in two temporary filesystem worlds):

```text
NEMISIS — LOCAL FIXTURE

CLAIM / TEST                               EXPECTED         BASE             CANDIDATE        VERDICT
regression-suite / baseline.reserve        INVARIANT        PASS             PASS             SUPPORTED
regression-suite / baseline.out-of-stock   INVARIANT        PASS             PASS             SUPPORTED
duplicate-retry / adversarial.duplicate    CHANGE_WITNESS   ASSERTION_FAIL   PASS             SUPPORTED
crash-retry / adversarial.crash-retry      CHANGE_WITNESS   ASSERTION_FAIL   ASSERTION_FAIL   UNRESOLVED

artifact: REJECTED — Candidate is incomplete: at least one required relation was not supported.
```

It also prints the digest of the immutable test bundle and the paths of the JSON manifest and the
static HTML report it wrote under `.nemisis/runs/<run-id>/`. The packaged candidate patch fixes an
ordinary duplicate request and keeps the repository's existing tests green, but still decrements
inventory twice when the first attempt crashes after its side effect. That fourth row is the whole
product: the patch looks done and is not.

`LOCAL FIXTURE` means observed local execution of checked-in inputs. It is not provider evidence.

## CrashCheck: the same failure, actually executed

Where `verify` reports an `UNRESOLVED` crash-retry row, CrashCheck goes and produces the
counterexample:

```bash
uv run nemisis check \
  --base fixture:sqlite-credit-v1/buggy \
  --candidate fixture:sqlite-credit-v1/misleading-green \
  --corrected fixture:sqlite-credit-v1/atomic \
  --mode local
```

The packaged SQLite case applies event `evt_1042`, which should grant one `$25` credit. The
misleading-green revision passes its small existing suite and an ordinary sequential duplicate
check, yet still reaches `$50` after a real `SIGKILL` and retry. The atomic revision ends at `$25`,
one ledger effect, and one processed marker under the same capsule. `PATCH_FAILED_STILL_REPRODUCES`
and exit `1` are the expected result.

Before reading the candidate, the run executes two fixed base-only hypotheses in parallel and
selects the reproducing `effect-commit` boundary. CrashCheck deletes that sole fault action and runs
the empty schedule in two fresh base worlds; both end exactly once, so deletion is rejected and this
one-action schedule is necessary for the fixture witness. This is not a general minimizer. It then
records five fresh proof worlds per supplied tree, exact source bindings, durable probes, confirmed
worker exits, new worker nonces, and final snapshots. CrashCheck does not run the fixture's ordinary
repository tests; `uv run nemisis benchmark` measures those separately as context for the
counterexample.

Replay the atomic revision using the exact `capsule:` path printed by `check`:

```bash
CAPSULE_PATH=.nemisis/repros/double-credit/PASTE_PRINTED_DIGEST/capsule.json
uv run nemisis replay "$CAPSULE_PATH" \
  --source fixture:sqlite-credit-v1/atomic --role corrected --mode local
```

CrashCheck uses `LOCAL` as the execution transport. The packaged audited contract and capsule carry
the separate `FIXTURE` truth label in the manifest and report. Neither label means `LIVE`.

### Open the one-minute evidence viewer

From the repository root, serve the committed static evidence:

```bash
uv run python -m http.server 8000
```

Open <http://127.0.0.1:8000/docs/assets/crashcheck-hero/> and select **Replay fixture evidence**.
The control reveals the committed, digest-bound `LOCAL` / `FIXTURE` receipt; it does not execute
repository code, call a model, or start a provider run. If either JSON binding fails, the viewer
shows no behavioral claim. The same files are readable without a server, starting at
[`docs/assets/crashcheck-hero/index.html`](docs/assets/crashcheck-hero/index.html).

### Point CrashCheck at a trusted repository

`init` writes strict JSON at `.nemisis/config.json`. A non-packaged contract stays `DRAFT` until you
accept its exact printed digest:

```bash
uv run nemisis init --issue issue.md --target app.credits:apply_credit --base main \
  --scenario sqlite-credit-v1
uv run nemisis init --issue issue.md --target app.credits:apply_credit --base main \
  --scenario sqlite-credit-v1 --accept-contract PASTE_PRINTED_DIGEST
uv run nemisis check --base main --candidate HEAD \
  --scenario .nemisis/config.json --mode local
```

Passing the reviewed config explicitly supports this pre-commit first run. Once the config is
committed on the base ref, the scenario ID loads only that exact base-owned copy; cwd and candidate
copies cannot override it.

Git refs are resolved to full commit SHAs. Fixture refs retain their exact fixture identity; local
directories are identified by their copied tree digest. Each `AnchorBinding` records the supplied
ref, resolved identity, and tree digest. `.git`, `.nemisis`, bytecode, and local pytest/mypy caches
are excluded from source materialization and cannot perturb the bound source tree.

Every CrashCheck command supports `--json`; progress stays on stderr. The exit policy is:

| Exit | Meaning |
| ---: | --- |
| `0` | `FIX_PROVEN_FOR_THIS_CAPSULE` |
| `1` | `BUG_REPRODUCED` or `PATCH_FAILED_STILL_REPRODUCES` |
| `2` | `EVIDENCE_INCOMPLETE`, `UNSUPPORTED_TARGET`, invalid input, or infrastructure failure |

Every run writes a manifest beneath `.nemisis/runs/<run-id>/`. Attempt-bearing runs add a report;
the golden path also records the full single-action deletion receipt. A pre-execution mapping
failure instead adds `anchor-resolution.json`. Immutable repro assets live under
`.nemisis/repros/double-credit/<capsule-digest>/`; completed runs add the executable
integration/fault regression. Stored paths are artifact-root-relative, so the bundle can move
without retaining a host path.

### In a pull request

Copy [the hardened example](.github/examples/crashcheck.yml) to `.github/workflows/crashcheck.yml`
and commit the accepted base-owned configuration. It pins Nemisis to a reviewed full commit SHA and
uses `pull_request`, read-only contents permission, credential-free checkout, a bounded job, a new
runner-temporary artifact directory, a job summary, and uploaded evidence. It refuses untrusted
forks, because local mode is not a hostile-code sandbox; those candidates stay blocked until
CrashCheck's ConTree transport exists.

## What it does

Every row below is exercised by the named test in this tree, with no network and no provider.

| Capability | Command or API | Test that proves it |
| --- | --- | --- |
| Runs one bundle against base and candidate worlds — real temp directories, real subprocesses — and reports the incomplete candidate | `nemisis verify --mode local` | [`tests/test_local.py`](tests/test_local.py) |
| Kills a real worker after its durable effect, replays the identical event in a fresh worker, and decides from durable state and process receipts | `nemisis check --mode local` | [`tests/test_crashcheck.py`](tests/test_crashcheck.py) |
| Replays an immutable Repro Capsule in five fresh worlds against a named source and role, and exports a regression that runs from a clean directory | `nemisis replay` | [`tests/test_crashcheck.py`](tests/test_crashcheck.py) |
| Measures the fixture's ordinary suites separately from the counterexample, under a strict result schema and digest | `nemisis benchmark` | [`tests/test_benchmark.py`](tests/test_benchmark.py) |
| Reports prerequisites independently instead of guessing — Python, POSIX `SIGKILL`, SQLite durability, live transport | `nemisis doctor` | [`tests/test_doctor.py`](tests/test_doctor.py) |
| Serves the committed evidence viewer fail-closed: it shows no behavioral claim unless both JSON bindings validate at runtime | `python -m http.server` | [`tests/test_static_hero.py`](tests/test_static_hero.py) |
| Classifies each claim as `SUPPORTED` / `REGRESSION` / `NON_DISCRIMINATING` / `UNRESOLVED` / `INCOMPLETE` from (expected relation, base outcome, candidate outcome) | `nemisis.matrix.classify` | [`tests/test_domain.py`](tests/test_domain.py) |
| Accepts a candidate only when every claim is supported *and* its evidence is complete | `nemisis.matrix.candidate_is_accepted` | [`tests/test_domain.py`](tests/test_domain.py) |
| Fails closed on stale, mismatched, or relabelled evidence — local evidence cannot be published as `LIVE` | `nemisis.evidence.validate_manifest` | [`tests/test_evidence.py`](tests/test_evidence.py) |
| Rejects unsafe patches: path traversal, harness/config paths, binary or mode-changing diffs; binds the patch to the base tree and the resulting tree digest | `nemisis.patches.validate_patch`, `nemisis.safety` | [`tests/test_safety.py`](tests/test_safety.py) |
| Reads outcomes only from a co-shipped pytest plugin's annotations; malformed, duplicate, unannotated, or oversized reports fail closed | `nemisis.junit.parse_junit` | [`tests/test_junit.py`](tests/test_junit.py) |
| Refuses to substitute local execution for live: `--mode live` lists its missing prerequisites and exits | `nemisis verify --mode live` | [`tests/test_cli.py`](tests/test_cli.py) |

## What it does not do

- **Your repository, in general.** Two packaged fixtures, plus one audited `sqlite-credit-v1` /
  `CreditStore` adapter for a trusted repository. No dependency-install step, no arbitrary handlers,
  databases, or languages, and no general schedule search.
- **A live provider run.** The Nemotron adapter and the ConTree sandbox adapter are tested against
  fakes and injected clients; [`docs/PROOF.md`](docs/PROOF.md) labels the Nemotron contract adapter
  `MOCKED` and the differential Nemotron + ConTree path
  `IMPLEMENTED_NOT_CURRENTLY_OBSERVED`. What is tested is the adapter's constraints — it holds model
  output to claims and test files, never commands, never an acceptance decision, and rejects unsafe
  generated paths or content ([`tests/test_nemotron.py`](tests/test_nemotron.py)). The provider call
  itself has never been made from this repository, and CrashCheck's own ConTree transport is
  `BLOCKED`: not implemented, and never silently downgraded to local.
- **Live mode, until you configure it yourself.** `--mode live` never substitutes local execution.
  It requires `NEBIUS_API_KEY` for Token Factory inference; a ConTree profile (`CONTREE_PROFILE`, or
  `~/.config/contree/auth.ini`); and `NEMISIS_CONTREE_ROOT_IMAGE` set to an immutable ConTree image
  UUID providing `/bin/sh`, `/bin/tar`, `/usr/bin/env`, `python` and `git` on the fixed system
  `PATH` plus an importable `pytest`. [`docs/STATUS.md`](docs/STATUS.md) records all three as absent
  here, so there is no current-tree `LIVE` or `RECORDED_LIVE` receipt; run
  `uv run nemisis doctor --mode live` for the independent prerequisite checks, and
  [`docs/LIVE_RUNBOOK.md`](docs/LIVE_RUNBOOK.md) for the exact prerequisites and blockers.
- **Sandboxing on your machine.** Local mode is temp directories and subprocesses, not isolation;
  it is safe because the fixtures are packaged and trusted, not because the runner confines them.
  Untrusted forks are refused rather than sandboxed. The boundary is written down in
  [`docs/SECURITY.md`](docs/SECURITY.md).
- **A hosted service or a demo video.** The evidence viewer is committed static files you serve
  yourself; there is no deployment, no judge API, no bounded repair attempt, and no recording.
- **Correctness or security proofs.** A finite bundle supports a claim only within its observed
  scope, and a capsule proves a fix only for that capsule.

## Where it fits

Nemisis is an instrument, not a merge gate you can buy today. Base-vs-candidate execution is not
new, and one tool already ships it: jittest, an independent open-source differential
test-execution gate, publishes a four-verdict vocabulary of its own that includes
`non_discriminating` — "test passes on both — proves nothing about the change" — as an output
verdict rather than a filtering step, and its published sweep reports 59 of 83 historical pull
requests as `inconclusive` because their environments could not be restored. In the published
literature, [SWE-bench](https://arxiv.org/abs/2310.06770) runs the same execution as a construction
filter and reports only the instances that survive; a 2026 differential-replay study of agent
rollouts ([arXiv 2607.28871](https://arxiv.org/abs/2607.28871)) reports the share of comparisons
carrying no bug-discriminating information, on benchmark tasks rather than merged pull requests.

What this tree adds is narrower than a new verdict. Verdicts are aggregated per claim rather than
per test: a claim is supported only when every test under it is supported, and the candidate is
accepted only when every claim is supported with complete evidence. One immutable bundle is bound
by digest to both worlds and to every execution receipt, and the manifest validator refuses a run
whose bindings, world lineage, or truth label do not match. CrashCheck narrows it further still:
the crash-retry row that the differential verifier can only mark `UNRESOLVED` becomes an executed
counterexample with a real kill, a real replay, and a capsule anyone can re-run.

A measurement study now in progress over real merged pull requests reuses this tree's fail-closed
JUnit rules — an `ERROR` is absence of evidence, a `SKIPPED` is never a pass — and its
`NON_DISCRIMINATING` concept, but publishes its verdicts in SWE-bench's terms (`FAIL_TO_PASS` /
`PASS_TO_PASS`); its method is `ventures/c-measurement/study/METHOD.md`, in a separate repository.
No results are published yet, and none are claimed here.

<!-- RELEASE-LINK: <package-name> -->

## Evidence

[`docs/PROOF.md`](docs/PROOF.md) is the ledger. It separates observed behavior from transport and
product claims, and every row names its exact evidence:

| Truth state | What is in it |
| --- | --- |
| `LOCAL` / `FIXTURE` / `VALID` | The confirmed kill and fresh-replay receipts, the five proof worlds per role, the measured benchmark, the committed viewer |
| `VERIFIED` | Candidate-blind witness selection, exact anchor mapping, fixture-scoped fault-action necessity, the Repro Capsule, installed-wheel replay, the project gates |
| `VERIFIED_WITH_BOUNDARY` | The GitHub composite Action — CI executes it, but remote-action download and real upload transfer are not exercised |
| `MOCKED` | The Nemotron contract adapter — injected-client structured-output tests only |
| `IMPLEMENTED_NOT_CURRENTLY_OBSERVED` | The differential Nemotron + ConTree path — bounded adapter and guest-receipt tests, no current-tree provider receipt |
| `BLOCKED` | CrashCheck's ConTree transport; any genuine current-tree live proof |
| `NOT_PROVIDED` / `UNSUPPORTED` | Hosted URL and demo video; arbitrary repositories, databases, languages, or general schedule search |

Release status is pinned by exact SHA, not by adjective. [`docs/STATUS.md`](docs/STATUS.md) records
the execution-critical engine commit, the clean source commit the evidence was measured from, the
commit that published it, and the engine, capsule, and benchmark digests — plus the linked CI runs
behind each gate. The evidence commit deliberately follows the measured source commit, so the
benchmark and manifest keep claiming the source they actually measured rather than the later
publication commit.

Truth labels are not interchangeable: `LIVE`, `RECORDED_LIVE`, `LOCAL`, `FIXTURE`, `MOCKED`,
`PLANNED` and `BLOCKED` keep their literal meanings in every evidence record. No fixture, mock,
historical result, or provider-looking ID is ever represented as `LIVE` or `RECORDED_LIVE`.

The product scope is in [`docs/PRODUCT.md`](docs/PRODUCT.md); the one authority path and its
boundaries are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); the measurement protocol is in
[`docs/BENCHMARK.md`](docs/BENCHMARK.md); the demo script is in [`docs/DEMO.md`](docs/DEMO.md); and
design trade-offs are in [`docs/DECISIONS.md`](docs/DECISIONS.md).

Reproduce the checks yourself:

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src tests
uv run pytest
uv build
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
