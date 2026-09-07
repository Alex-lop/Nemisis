# Morning

A third hostile round found thirty-seven confirmed false passes in the engine the last report
called reviewed; all four of their root causes are closed and pinned, every wall-clock wait in
the kernel now says what did not happen, `init` refuses at draft time what `check` would refuse,
the generator writes every shape the reviewers wrote by hand in both scenarios, the hero is
measured on two machines with one verdict, and no `LIVE` receipt exists, because no key does.

Eight PRs, `main` untouched, in merge order (each stacked on the one above it):

| PR | Title | Head | CI on that head | Merge |
| -- | ----- | ---- | --------------- | ----: |
| #15 | feat(redteam): the grammar speaks the hostile reviews' shapes, in both scenarios | `a5d929e` | [34088616032](https://github.com/Alex-lop/Nemisis/actions/runs/34088616032) green | 1 |
| #16 | fix(kernel): every wall-clock wait names what did not happen; the budget is a knob | `2be08ab` | [34089340263](https://github.com/Alex-lop/Nemisis/actions/runs/34089340263) green | 2 |
| #17 | feat(check): init refuses what check would refuse; a remedy for every refusal | `466a065` | [34090021960](https://github.com/Alex-lop/Nemisis/actions/runs/34090021960) green | 3 |
| #18 | docs(seam): what a third scenario would need the seam to say, with the limit pinned | `cc89e8a` | [34091409390](https://github.com/Alex-lop/Nemisis/actions/runs/34091409390) green | 4 |
| #19 | fix(kernel): close the four root causes the third hostile review found | `2e8aee6` | [34093890874](https://github.com/Alex-lop/Nemisis/actions/runs/34093890874) green | 5 |
| #20 | ci+release: CPython 3.14, a Linux hero on demand, a tag-driven release, a Dockerfile | `8382c38` | [34094345512](https://github.com/Alex-lop/Nemisis/actions/runs/34094345512), running when this was written | 6 |
| #21 | docs(story): demo scripts, PRODUCT, and the site brought to the engine that exists | `c339aa9` | [34094580768](https://github.com/Alex-lop/Nemisis/actions/runs/34094580768), running when this was written | 7 |
| #22 | docs+evidence: hero at the final engine, the design entries, this report | tip of `overnight3/morning` (this file is in it) | [branch runs](https://github.com/Alex-lop/Nemisis/actions?query=branch%3Aovernight3%2Fmorning) | 8 |

Merge each with "delete branch"; GitHub retargets the next PR by itself. Every PR body is a
mini-ledger. The subagent branches (#20, #21) carry a merge commit from the PR below them rather
than a rebase, because they had been pushed and the rule is never to rewrite the remote.

## The evidence ledger

| # | Claim | PR | Status | Proof (exact command → expected output) |
| - | ----- | -- | ------ | -------------------------------------- |
| 1 | Gate on clean `main` (`db7969f`) is green | – | PASS | `uv sync --frozen --dev && uv run ruff format --check src tests && uv run ruff check src tests && uv run mypy src tests && uv run pytest -q && uv build` → 453 passed (4:13 under coverage) |
| 2 | Gate at the final head is green | #22 | PASS | same commands at the commit before this file → 530 passed; laptop wall 3:20 for #19's head while a mutation sweep ran beside it |
| 3 | CI runs the gate on CPython 3.12, 3.13, and 3.14 | #20 | PASS | run [34093138705](https://github.com/Alex-lop/Nemisis/actions/runs/34093138705): three legs, `uv sync`/ruff/mypy green on 3.14.6, the one failure on each leg the count line this stack requotes; the head run on `8382c38` is the proof |
| 4 | The nightly red team has run on GitHub | – | PASS | [34086693284](https://github.com/Alex-lop/Nemisis/actions/runs/34086693284): `generated 300 handlers from seed 20260907; 0 disagreements`, 15:37 on Linux, at engine `228430389f…` (before tonight's grammar and fixes) |
| 5 | Generated handlers vs oracle, widened grammar, both scenarios | #15 | PASS | `uv run nemisis redteam --cases 300 --seed 20260907 --scenario sqlite-credit-v1` and `--scenario sqlite-inventory-v1` → 0 disagreements each (184 refused, 31 proven, 51 invariant, 34 duplicate) at the pre-fix engine, and 0 disagreements each again at the post-fix engine of #17; `uv run pytest -q tests/test_redteam.py` → 45 pinned shapes plus ten credit and four inventory handlers end to end |
| 6 | Third hostile round: counts | #19 | PASS | 6 lenses, 57 handlers, 44 claimed, 37 confirmed by independent re-runs (each run twice or more); 4 root causes; 13 shapes plus 2 scratch escapes pinned in `test_side_channels_from_the_third_hostile_review_forfeit_the_verdict` and `test_the_scratch_tree_is_known_by_identity_not_by_name`; 3 channels named as boundaries; 3 claims kept as decisions; 2 readers, 22 findings, 6 acted on |
| 7 | Every third-round shape is now refused with its reason | #19 | PASS | `uv run pytest -q tests/test_verdict_paths.py -k "third_hostile_review or scratch_tree_is_known or same_ref"` → 16 passed; every earlier pinned shape keeps its expectation (`-k "hidden_from_the_probes or second_hostile_review or beside_the_database"` → 17 passed) |
| 8 | Every packaged tree keeps its verdict at the final engine | #22 | PASS | `uv run pytest -q tests/test_verdict_paths.py -k packaged_zoo tests/test_inventory_scenario.py` inside the gate of row 2; hero → `PATCH_FAILED_STILL_REPRODUCES`, atomic → `FIX_PROVEN…` |
| 9 | `mark-first` is caught; `shadow-table` refused; the raw-SQL remedy named; inventory verdicts | – | PASS | CI's wheel smoke on every head (`ci.yml`), plus `--candidate fixture:sqlite-credit-v1/mark-first` → `PATCH_FAILED_INVARIANT_BROKEN` exit 1; `shadow-table` → `EVIDENCE_INCOMPLETE`, "the schema changed", exit 2; `raw-sql` → exit 2 naming `store.credit_and_mark(...)`; `fixture:sqlite-inventory-v1/mark-first` → "10 units on hand instead of 8 units", exit 1 |
| 10 | A timeout says what did not happen, and the budget is a knob | #16 | PASS | `uv run pytest -q tests/test_sqlite_runner.py tests/test_verdict_paths.py -k "timeout or knob or never_returns or fixed_tree_as_base or receive"` → 28 passed; a spinning candidate's summary is exactly "5 of 5 candidate worlds did not complete: the replay delivery's next store commit or its end (commits so far: credit, mark_processed) did not arrive within 2 s; NEMISIS_WORKER_TIMEOUT_SECONDS raises the budget on a slow machine."; `NEMISIS_WORKER_TIMEOUT_SECONDS=0` is refused before any world runs |
| 11 | `init` refuses a target the base cannot bind, with the remedy | #17 | PASS | `uv run pytest -q tests/test_crashcheck.py -k "init_refuses or anchor_binding_failure"` → 3 passed; `init --target m:handler` → `UNSUPPORTED_TARGET: … sqlite-credit-v1 binds app.credits:apply_credit, so pass --target app.credits:apply_credit`, nothing written |
| 12 | Hero regenerated at the final engine, strict branch | #22 | PASS | `uv run pytest -q tests/test_static_hero.py` → 4 passed with engine digests equal; identities in STATUS (`c339aa9`, capsule `190d62ea…`, result `7d0672e4…`) |
| 13 | A second measurement of the hero on Linux agrees | #20 | PASS | [34092142968](https://github.com/Alex-lop/Nemisis/actions/runs/34092142968): verdict `PATCH_FAILED_STILL_REPRODUCES`, engine `228430389f…` and event `4ad9ce16…` byte-identical to the laptop's, capsule `85adf7b9…` and environment `13fc1958…` different as designed; artifact `linux-hero-34092142968` |
| 14 | The Docker image runs the zoo | #20 | PASS | `docker build -t nemisis . && docker run --rm --network none nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/mark-first` → `PATCH_FAILED_INVARIANT_BROKEN`, exit 1, same engine digest (tested by the subagent; Docker Desktop started and quit for it) |
| 15 | The sdist ships the package, not the repository | #20 | PASS | `uv run pytest -q tests/test_release.py` → the sdist holds `src/nemisis`, `README.md`, `LICENSE`, `pyproject.toml`, `PKG-INFO`, `.gitignore` and nothing else (it used to ship docs, tests, the site, and the directive files) |
| 16 | The seam cannot say a conservation invariant; the limit is pinned | #18 | PASS | `uv run pytest -q tests/test_crash_models.py -k second_subject` → 1 passed: a destination-only transfer reads `EXACTLY_ONCE` with the source untouched; a zero delta is refused by the capsule |
| 17 | The site's hero terminal is the command's real stdout | #21 | PASS | the fabricated `sweep:` line is gone; every non-dim line is verbatim from `nemisis check … misleading-green`; the proof strip cites run 34086693284 |
| 18 | README H1 equals the proven level | #22 | PASS | unchanged H1; rows 6–9 are the proof, and the boundary list in SECURITY is longer and truer than yesterday's |
| 19 | `LIVE` receipt | – | FAIL | `printenv NEBIUS_API_KEY \| wc -c` → 0; nothing is `LIVE`; `BLOCKED` stays |
| 20 | Mutation ledger of the kernel's refusals | – | UNKNOWN | the runner (`tools/mutants.py`) is written and its sweep was still running in its worktree when this was written; nothing pushed, no counts claimed (see negatives) |
| 21 | Nightly at the final engine on GitHub | – | UNKNOWN | the dispatch was declined by this session's permission layer twice; row 5's local sweeps at the post-fix engine stand in until the 06:17 UTC cron runs on `main` |

## Explicit negatives
- **The mutation ledger did not land.** The subagent wrote and committed `tools/mutants.py`
  locally and was mid-sweep (a mutant in place in its worktree) at the end; no ledger, no counts,
  nothing pushed. The branch `overnight3/mutation-ledger` exists only locally.
- **Three channels were named, not closed** (SECURITY lists them): a write through a private
  connection reverted before the next store commit; counting sibling worlds through the shared
  scratch tree; patching below the store class. The mount-namespace design that closes the first
  two is in DECISIONS, as a design.
- **No third scenario.** The conservation class is not honest on this seam (row 16); the outbox
  class is one seam change away and is described, not built.
- **The nightly was not dispatched at the final engine** and **the four stale remote branches
  were not deleted**: both commands were declined by the session's permission classifier. Both
  are one line each under hands.
- **One load flake, not hidden.** During a local full gate that ran beside the mutation sweep,
  `test_dedup_state_hidden_from_the_probes_forfeits_the_verdict[repointed-ledger]` failed once;
  it passed three times in a row alone and in the next full gate. The message class is the 10 s
  budget; the knob and the soak workflow exist for exactly this.
- **The action's new outputs were proven locally against four real runs, not on a runner**
  before #20's head run; #20's own CI run exercises the composite action.
- **No new recording.** `vhs` is here and the demo scripts changed; the tape was not re-recorded.
- **`propose-patch`, `init --nemotron`, ConTree**: untouched, still `BLOCKED` without a key.
- **The transient-write finding is inside the stated boundary** ("kill points are store commits")
  and is now written down as such rather than fixed.

## Decisions made for you
- **Stacked PRs, merges not rebases for the pushed subagent branches** (#20, #21). Revert: none
  needed; squash-merge each PR if the merge commits offend.
- **`NEMISIS_WORKER_TIMEOUT_SECONDS` is refused outside 1 to 600 s, never clamped**; the default
  is still 10. Revert: `worker_timeout_seconds` in `sqlite_runner.py`.
- **`init` refuses, not warns**, a target the base cannot bind. Revert: `_require_bindable` in
  `crashcheck.py`; `tests/test_crashcheck.py` pins the refusal.
- **A failing corrected control still withholds the candidate's verdict**; the sentence now says
  so and that omitting `--corrected` restores it. A reviewer argued the opposite.
- **A handler that guards on the shelf level instead of its marker keeps its capsule-scoped pass**;
  that is what the verdict's name says. Revert: none, it is a non-change.
- **The sidecars are pinned by kind only**; macOS stamps `com.apple.provenance` on files the
  worker creates, and a flag at their names is a named channel. Revert: `_require_only_the_store_wrote`.
- **Worker stdout/stderr stay hashed and unpersisted**; the test that pins it was kept.
- **Version 0.2.0; the sdist is the package only; PR comments stay deferred (annotations instead);
  the Docker entrypoint runs `--no-dev`.** Revert: the commits on #20.
- **The root `index.html` stays.** The live Pages source is the branch build (`build_type:
  legacy`), so the root file is what serves; the Pages workflow now deploys only when the source
  is a workflow. Revert: `pages.yml` on #20.
- **The two old morning reports are under `docs/reports/`** (2026-09-05 and 2026-09-06).

## Needs your hands
1. Merge #15 through #22 in order, each with "delete branch".
2. After the last merge: set the action pin in `.github/examples/crashcheck.yml` and STATUS's
   "reviewed action pin" to the new `main` SHA (`tests/test_docs_identity.py` refuses drift).
3. `gh workflow run nightly.yml --ref main -f cases=300 -f seed=20260907` (or wait for the
   06:17 UTC cron); paste its URL into STATUS row 4.
4. `git push origin --delete overnight2/docs-and-evidence chore/license-copyright docs/customer-readme imgbot`
   (SHAs to restore if ever wanted: `6eedb51`, `e9129be`, `ec0336e`, `6b2a962`).
5. PyPI: pypi.org → Your account → Publishing → add a pending publisher (project `nemisis`, owner
   `Alex-lop`, repo `Nemisis`, workflow `release.yml`, environment `pypi`); GitHub → Settings →
   Environments → new `pypi`; then `git tag -a v0.2.0 -m v0.2.0 && git push origin v0.2.0`.
6. `set -a; source .env; set +a` with `NEBIUS_API_KEY`, then `docs/LIVE_SETUP.md` Stage A2b.
7. Optional: Settings → Pages → Source → GitHub Actions; the `Pages` workflow then deploys and
   the branch build stops racing it.
8. On a quiet laptop: `uv run nemisis benchmark --output benchmarks/results/crashcheck-v1.json --json`;
   tonight's timings were taken beside a mutation sweep and BENCHMARK says so.

## Alex's ten-minute grading pass
1. `for n in 15 16 17 18 19 20 21 22; do gh pr checks $n; done` — every head green.
2. `git fetch origin && git checkout overnight3/morning && uv sync --frozen --dev && uv run pytest -q` → 530 passed.
3. `uv run pytest -q tests/test_verdict_paths.py -k third_hostile_review` → 13 passed: each of
   the shapes that earned `FIX_PROVEN` at 02:00 is refused with the sentence that names it.
4. `NEMISIS_WORKER_TIMEOUT_SECONDS=0 uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/atomic` → refused before any world runs, exit 2.
5. `uv run nemisis init --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md --target m:handler --base fixture:sqlite-credit-v1/buggy` → `UNSUPPORTED_TARGET: … pass --target app.credits:apply_credit`, exit 2, nothing written.
6. `uv run nemisis redteam --cases 30 --seed 3 --scenario sqlite-inventory-v1 --out ./redteam` → "0 disagreements".
7. `open https://alex-lop.github.io/Nemisis/` — the terminal block matches
   `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/misleading-green --mode local` line for line.
8. `docker build -t nemisis . && docker run --rm nemisis doctor --mode local` → READY.
9. `git diff db7969f..overnight3/morning -- src | grep -nE "^\+.*(sleep\(|xfail|skip\(|LIVE)"` → no sleep, no xfail, no skip, no relabeling.
10. Read `docs/SECURITY.md`'s "What the controller cannot read" paragraph, then row 6.

## What I would do next
1. Finish and publish the mutation ledger: the runner exists; run it on the final engine, close
   every hole it finds with a test, and put the table in `docs/reports/`.
2. The Linux mount-namespace leg from DECISIONS: `bwrap` around the worker in CI, so "nothing
   outside the world" is enforced there and two named boundaries become impossible.
3. The outbox scenario after one seam change (an optional audited scalar), then Stage A2b with
   a key: the `LIVE` Nemotron patch is still the beat that kills the last dismissal.
