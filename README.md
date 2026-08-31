# Nemisis

Nemisis makes an AI-generated patch prove each claim: one identical test bundle is run against a
base snapshot and a candidate snapshot in separate throwaway directories, and each claim gets a
verdict from the pair of outcomes. It never pushes, merges, comments, or opens a PR, and it never
modifies your working tree or your git history: it runs in temporary directories, writes one run
directory — `.nemisis/runs/` under the directory you run it from, or wherever `--output-dir`
points — and prints a decision instead of taking one.

**Scope today, before you install anything.** The engine runs exactly one packaged fixture
(`idempotency-retry`); arbitrary repositories are not supported. The Nemotron claim-generation path
and the ConTree sandbox path are implemented and contract-tested against fakes only — neither has
ever reached a live provider from this repository. The full list is under "What it does not do".

## Install and run

Python 3.12+ and [uv](https://docs.astral.sh/uv/). Clone this repository, then from its root:

```bash
uv sync --frozen
uv run nemisis verify --fixture idempotency-retry --mode local
```

Output observed 2026-08-31 UTC from this commit's tree (run id and absolute paths elided; the run
performs real `pytest` subprocesses in two temporary filesystem worlds):

```text
NEMISIS — LOCAL FIXTURE
bundle: 70e10c52e50c143b526af020c37aee2ee4bce0da85453bb1470d42736895b725

CLAIM / TEST                               EXPECTED         BASE             CANDIDATE        VERDICT
regression-suite / baseline.reserve        INVARIANT        PASS             PASS             SUPPORTED
regression-suite / baseline.out-of-stock   INVARIANT        PASS             PASS             SUPPORTED
duplicate-retry / adversarial.duplicate    CHANGE_WITNESS   ASSERTION_FAIL   PASS             SUPPORTED
crash-retry / adversarial.crash-retry      CHANGE_WITNESS   ASSERTION_FAIL   ASSERTION_FAIL   UNRESOLVED

artifact: REJECTED — Candidate is incomplete: at least one required relation was not supported.
```

It also prints the paths of the JSON manifest and the static HTML report it wrote under
`.nemisis/runs/<run-id>/`. The packaged candidate patch fixes an ordinary duplicate request and
keeps the repository's existing tests green, but still decrements inventory twice when the first
attempt crashes after its side effect. That fourth row is the whole product: the patch looks done
and is not.

## What it does

Every row below is exercised by the named test in this tree, with no network and no provider.

| Capability | Command or API | Test that proves it |
| --- | --- | --- |
| Runs one bundle against base and candidate worlds — real temp directories, real subprocesses — and reports the incomplete candidate | `nemisis verify --mode local` | [`tests/test_local.py`](tests/test_local.py) |
| Classifies each claim as `SUPPORTED` / `REGRESSION` / `NON_DISCRIMINATING` / `UNRESOLVED` / `INCOMPLETE` from (expected relation, base outcome, candidate outcome) | `nemisis.matrix.classify` | [`tests/test_domain.py`](tests/test_domain.py) |
| Accepts a candidate only when every claim is supported *and* its evidence is complete | `nemisis.matrix.candidate_is_accepted` | [`tests/test_domain.py`](tests/test_domain.py) |
| Fails closed on stale, mismatched, or relabelled evidence — local evidence cannot be published as `LIVE` | `nemisis.evidence.validate_manifest` | [`tests/test_evidence.py`](tests/test_evidence.py) |
| Rejects unsafe patches: path traversal, harness/config paths, binary or mode-changing diffs; binds the patch to the base tree and the resulting tree digest | `nemisis.patches.validate_patch`, `nemisis.safety` | [`tests/test_safety.py`](tests/test_safety.py) |
| Reads outcomes only from a co-shipped pytest plugin's annotations; malformed, duplicate, unannotated, or oversized reports fail closed | `nemisis.junit.parse_junit` | [`tests/test_junit.py`](tests/test_junit.py) |
| Refuses to substitute local execution for live: `--mode live` lists its missing prerequisites and exits | `nemisis verify --mode live` | [`tests/test_cli.py`](tests/test_cli.py) |

## What it does not do

- **Your repository.** One packaged fixture, no dependency-install step, no arbitrary-repo intake.
- **A live provider run.** The Nemotron adapter and the ConTree sandbox adapter are tested against
  fakes; `docs/PROOF.md` labels them `MOCKED_TEST_ONLY`. What is tested is the adapter's
  constraints — it holds model output to claims and test files, never commands, never an acceptance
  decision, and rejects unsafe generated paths or content
  ([`tests/test_nemotron.py`](tests/test_nemotron.py)); the provider call itself has never been made
  from this repository, and a genuine current-tree call is `BLOCKED`.
- **Live mode, until you configure it yourself.** `--mode live` never substitutes local execution.
  It requires `NEBIUS_API_KEY` for Token Factory inference; a ConTree profile (`CONTREE_PROFILE`, or
  `~/.config/contree/auth.ini`); and `NEMISIS_CONTREE_ROOT_IMAGE` set to an immutable ConTree image
  UUID providing `/bin/sh`, `/bin/tar`, `/usr/bin/env`, `python` and `git` on the fixed system
  `PATH` plus an importable `pytest`. That root-image contract is `NOT_PROVEN`: `docs/STATUS.md`
  records that it has never been checked against an account.
- **Sandboxing on your machine.** Local mode is temp directories and subprocesses, not isolation;
  it is safe because the fixture is packaged and trusted, not because the runner confines it.
- **A CI check, a service, or a hosted demo.** No GitHub integration, no web server, no repair
  attempt, no video.
- **Correctness or security proofs.** A finite bundle supports a claim only within its observed
  scope.

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
whose bindings, world lineage, or truth label do not match.

A measurement study now in progress over real merged pull requests reuses this tree's fail-closed
JUnit rules — an `ERROR` is absence of evidence, a `SKIPPED` is never a pass — and its
`NON_DISCRIMINATING` concept, but publishes its verdicts in SWE-bench's terms (`FAIL_TO_PASS` /
`PASS_TO_PASS`); its method is `ventures/c-measurement/study/METHOD.md`, in a separate repository.
No results are published yet, and none are claimed here.

<!-- RELEASE-LINK: <package-name> -->

## Evidence

| Class | What is in it | Where |
| --- | --- | --- |
| `VERIFIED_LOCAL` | Domain and digest bindings, patch/generated-file boundaries, differential fixture worlds, immutable bundle equality, the exact matrix above | [`docs/PROOF.md`](docs/PROOF.md) |
| `MOCKED_TEST_ONLY` | Nemotron adapter, ConTree adapter — contract tests against fakes | [`docs/PROOF.md`](docs/PROOF.md) |
| `BLOCKED` | Genuine current-tree Nemotron call, genuine ConTree run | [`docs/STATUS.md`](docs/STATUS.md) |
| `NOT_PROVEN` | Arbitrary-repository result channel, bounded repair, judge API, hosted demo | [`docs/PROOF.md`](docs/PROOF.md) |

The one authority path and its boundaries are in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md);
the demo script is in [`docs/DEMO.md`](docs/DEMO.md); design trade-offs are in
[`docs/DECISIONS.md`](docs/DECISIONS.md). Truth labels are not interchangeable: `LIVE`,
`RECORDED_LIVE`, `LOCAL`, `FIXTURE`, `MOCKED`, `PLANNED` and `BLOCKED` keep their literal meanings
in every evidence record.

Reproduce the checks yourself:

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src tests
uv run pytest
```

## License

Apache-2.0 — see [LICENSE](LICENSE).
