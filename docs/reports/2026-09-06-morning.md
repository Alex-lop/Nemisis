# Morning

CrashCheck now attributes everything it can read of the database and of the directory a worker
runs in and names the two channels it cannot, judges two scenarios with one kernel, is red-teamed
by a generator on every CI run, and tells a judge who writes raw SQL the one-line change; no `LIVE`
receipt exists, because no key does.

Ten PRs, `main` untouched, in merge order:

| PR | Title | Head | CI on that head | State | Merge |
| -- | ----- | ---- | --------------- | ----- | ----: |
| #5 | ci: run the gate on CPython 3.12 and 3.13 | `a6a4801` | [34011484455](https://github.com/Alex-lop/Nemisis/actions/runs/34011484455) (both legs, at `13fe088`) + head run green | ready | 1 |
| #6 | ci(pages): stage the viewer for GitHub Pages, fail-closed until enabled | `e84ff7e` | [34011486985](https://github.com/Alex-lop/Nemisis/actions/runs/34011486985) | staged: needs the Pages toggle | 2 |
| #7 | fix(action): re-pin the example workflow; guard the pin | `0cd0bf3` | [34011609883](https://github.com/Alex-lop/Nemisis/actions/runs/34011609883) | ready | 3 |
| #8 | test: the README's point-it-at-your-code sequence on a real git repo | `62079a7` | [34011612193](https://github.com/Alex-lop/Nemisis/actions/runs/34011612193) | ready, stacked on #7 | 4 |
| #9 | feat(zoo): the raw-SQL judge handler earns a remedy, not a trap | `3a02ed7` | [34012175516](https://github.com/Alex-lop/Nemisis/actions/runs/34012175516) | ready, stacked on #8 | 5 |
| #10 | refactor(scenario): the Scenario seam, zero behavior change | `cfcdea4` | [34012509943](https://github.com/Alex-lop/Nemisis/actions/runs/34012509943) | ready, stacked on #9 | 6 |
| #11 | feat(scenario): generic receipts + sqlite-inventory-v1 | `db37ae8` | [34013254317](https://github.com/Alex-lop/Nemisis/actions/runs/34013254317) | ready, stacked on #10 | 7 |
| #12 | feat(redteam): grammar, oracle, nightly sweep | `883841b` | [34013915213](https://github.com/Alex-lop/Nemisis/actions/runs/34013915213) | ready, stacked on #11 | 8 |
| #13 | fix(kernel): attribution is the whole database and the whole world | `14cd428` | [34043689355](https://github.com/Alex-lop/Nemisis/actions/runs/34043689355) (the first head `5c7590b` was green on [34014576360](https://github.com/Alex-lop/Nemisis/actions/runs/34014576360)) | ready, stacked on #12 | 9 |
| #14 | docs+evidence: claims sweep, hero regenerated, this report | tip of `overnight2/docs-and-evidence` (this file is in it, so it cannot quote its own SHA) | [branch runs](https://github.com/Alex-lop/Nemisis/actions?query=branch%3Aovernight2%2Fdocs-and-evidence), queued when this was pushed | ready, stacked on #13 | 10 |

Merge each with "delete branch"; GitHub retargets the next PR to `main` by itself. Every PR body is
a mini-ledger (what, why, proof, not-done, revert).

## The evidence ledger

| # | Claim | PR | Status | Proof (exact command → expected output) |
| - | ----- | -- | ------ | -------------------------------------- |
| 1 | Gate on clean `main` (`4db4213`) is green | – | PASS | `uv sync --frozen --dev && uv run ruff format --check src tests && uv run ruff check src tests && uv run mypy src tests && uv run pytest -q && uv build` → 364 passed; laptop wall 1:43 (pytest 100.9 s) |
| 2 | Gate at the final head is green | #14 | PASS | same commands at the commit before this file was added → 453 passed; laptop wall 2:32 (pytest 2:30) |
| 3 | CI runs the gate on CPython 3.12 and 3.13 | #5 | PASS | run 34011484455: `verify (3.12)` 4m5s, `verify (3.13)` 3m49s, both green |
| 4 | The example workflow's pin equals the reviewed pin STATUS names | #7 | PASS | `uv run pytest -q tests/test_docs_identity.py` → 3 passed; `grep -n "Nemisis@" .github/examples/crashcheck.yml` → `4db42137…`; the same SHA on STATUS's "reviewed action pin" line |
| 5 | README's init → accept → check runs on a real git repo through the CLI, digest parsed from stdout | #8 | PASS | `uv run pytest -q tests/test_point_at_your_code.py` → 1 passed (exit 0 `FIX_PROVEN…` on the fix branch, exit 1 `PATCH_FAILED_STILL_REPRODUCES` on the rewrite) |
| 6 | `uv tool install "git+https://github.com/Alex-lop/Nemisis@main"` works | – | PASS | installed in 3.9 s into a scratch tool dir; `nemisis doctor --mode local` → READY; `nemisis check … --candidate fixture:sqlite-credit-v1/mark-first` → `PATCH_FAILED_INVARIANT_BROKEN` at engine `99ef8ade…` |
| 7 | Every packaged credit tree keeps its verdict at the final engine | #14 | PASS | `uv run pytest -q tests/test_verdict_paths.py -k packaged_zoo` → 3 passed; `tests/test_crashcheck.py` hero → `PATCH_FAILED_STILL_REPRODUCES`; atomic → `FIX_PROVEN…` |
| 8 | The sweep still catches `mark-first` | #14 | PASS | `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/mark-first` → `PATCH_FAILED_INVARIANT_BROKEN`, "commit 1 of 2 (mark_processed)", exit 1 |
| 9 | Attribution refuses a write around the store | #13 | PASS | `--candidate fixture:sqlite-credit-v1/shadow-table` → `EVIDENCE_INCOMPLETE`, integrity `INVALID`, "the schema changed (a table, index, or trigger this scenario did not seed)", exit 2 |
| 10 | Eleven hidden-flag shapes from two hostile reviews are refused | #13 | PASS | `uv run pytest -q tests/test_verdict_paths.py -k "hidden_from_the_probes or shadow_table or other_account or second_hostile_review or scratch_tree or schedule"` → 21 passed (table, three header fields, rowid, free pages, `../` and `../../..` files, empty dir, `~`, `TMPDIR`, `__pycache__`, tree dir, mode bits, deleted-on-exit, re-pointed row, renamed table, split schedule, BLOB) |
| 11 | The raw-SQL judge handler gets a remedy, not a trap | #9 | PASS | `--candidate fixture:sqlite-credit-v1/raw-sql` → `EVIDENCE_INCOMPLETE`, summary names `store.credit_and_mark(account_id, event_id, amount_cents)` and `docs/PRODUCT.md#the-store-api`, exit 2; CI smokes it from the wheel |
| 12 | The Scenario seam changed no behavior | #10 | PASS | `f1_equivalence.py` (pasted below): six trees, verdict/exit/summary/axes/hunt/capsule/manifest/repro dir all IDENTICAL between `3a02ed7` and `cfcdea4` |
| 13 | Second scenario: buggy / atomic verdicts | #11 | PASS | `--base fixture:sqlite-inventory-v1/buggy --candidate …/misleading-green` → `PATCH_FAILED_STILL_REPRODUCES` (6 units), exit 1; `…/atomic` → `FIX_PROVEN…` (8 units), exit 0; `…/mark-first` → `PATCH_FAILED_INVARIANT_BROKEN` (10 units, marked), exit 1; base replay → `BUG_REPRODUCED` |
| 14 | Second scenario is not a renamed copy | #11 | PASS | seed 10 not 0, effect −2 not +2500, predicate on `reservations`/`reserved_orders`; `uv run pytest -q tests/test_inventory_scenario.py` → 9 passed |
| 15 | Generated handlers vs oracle: normal suite | #12 | PASS | `uv run pytest -q tests/test_redteam.py` → 30 passed (10 generated cases, 0 disagreements) |
| 16 | Generated handlers vs oracle: local sweeps | #12/#13 | PASS | 60 cases seed 11 → 0 disagreements (after one oracle bug, case 44, was fixed and pinned); 300 cases seed 2026 at `5c7590b` → 0 disagreements (8:39 under load); 300 cases at the final engine `14cd428` → 0 disagreements (6:04) |
| 17 | Hostile review counts | #9–#13 | PASS | #9+#10: 13 handlers, 23 findings, 20 confirmed (5 false passes → #13); #11: 21 handlers, 16 findings, 13 confirmed (mkdir flag, table flag, `user_version`, parent-directory file, 9 wording/validator items) → all in #13; #13: 7 handlers, 15 findings, 12 confirmed (journal-mode bits, rowid, free pages, schema cookie, deleted-on-exit file, `__pycache__`, tree directory, mode bits, `-shm` name, `../../..`, BLOB TypeError, prose) → 10 closed in #13's second commit, 2 named as the boundary |
| 18 | README H1 equals the proven level | #14 | PASS | H1: "CrashCheck proves an AI patch survives a real crash, not just that its tests pass." (unchanged: every handler shape a judge or two hostile reviews could write either fails for its real reason or is refused with the reason named); rows 7–10 are the proof |
| 19 | `LIVE` receipt | – | FAIL | `printenv NEBIUS_API_KEY \| wc -c` → 0; nothing is `LIVE`; `BLOCKED` stays |
| 20 | GitHub Pages public URL | #6 | UNKNOWN | Pages is not enabled (`gh api repos/Alex-lop/Nemisis/pages` → 404); the workflow is green and skips deploy until it is |
| 21 | Hero regenerated at the final engine | #14 | PASS | `uv run pytest -q tests/test_static_hero.py` → 2 passed on the strict branch (engine digest equal); identities in STATUS |
| 22 | pytest-xdist | – | not done, by rule | the laptop gate was 1:43 < 4 min at the start (2:32 (pytest 2:30) at the end after +89 tests; still under) |

## Explicit negatives
- **This report is late.** The reviews ran hours longer than the code; the engine fix they produced (#13) was worth it. Everything above is pushed; nothing was rushed past its gate.
- **Two channels stay outside local mode's sight**, named in `docs/SECURITY.md`: a flag the store's own next commit overwrites (file mtime, WAL bytes) and a flag at the `-wal`/`-shm` names. In-process instrumentation attributes what it can read; the docs now list exactly what it reads.
- **#13's second commit was not re-reviewed by a third hostile round** (time); its tests pin every shape the second round found.
- **One flaky observation, not hidden.** While recording the pytest still with 65 MB of memory free (the first recording was killed by the OS for memory), `tests/test_inventory_scenario.py::test_the_hero_story_holds_for_a_decrement` came back `EVIDENCE_INCOMPLETE` instead of `PATCH_FAILED_STILL_REPRODUCES` once. Three solo reruns and the full gate afterwards passed (453/453); the still was re-recorded. The likely path is the worker's 10 s hello timeout under memory starvation; it is unchanged and unwidened. Row 2 stands on the gate, not on the still.
- No `LIVE` anything: `NEBIUS_API_KEY` is absent on this machine (0 bytes). `BLOCKED` stays; Stage A is one command away.
- ConTree transport (K): not started; E–H took the night and the hostile review produced an engine fix that was worth more.
- Pages: staged, not enabled, no URL claimed.
- The generator covers the credit scenario only; the inventory grammar is a table away.
- Durable state by absolute path elsewhere on the machine (`/var/tmp/x`) is still invisible and documented.
- A first 300-case sweep was invalid: I removed a worktree under it mid-run. The reported sweeps are reruns.
- The imgbot PR #3 is closed; PR #2 was already closed before tonight (salvage below).
- xdist not added (threshold not met); a parallel run would multiply concurrent kill worlds under a fixed 10 s IPC timeout.

## Decisions made for you
- **Message-only for raw SQL (E option 1), not a `store.transaction()` primitive.** A raw-SQL surface on the store's database widens the trust boundary for no gain; `credit_and_mark` already is the one-line atomic form. Revert: none needed; to add the primitive, extend `StoreBase` and `Scenario.apply`.
- **Receipts renamed generically** (`StateSnapshot.subject_total`…, `effect_delta`, capsule `event`). The old hero JSON no longer validates against the strict models; it was regenerated. Revert: `git revert 3ece6b3` and every commit after it.
- **`sqlite_credit.py` renamed to `sqlite_runner.py`, runner id `sqlite-runner-v2`.** Old capsules say `sqlite-credit-runner-v1` and are refused with "run check again". Revert: `git mv` back and restore the two constants.
- **CLI infers the scenario from a fixture base ref**; an explicit mismatch is refused. Revert: set the three `--scenario` defaults back to `sqlite-credit-v1`.
- **Each world is a directory with `HOME` and `TMPDIR` inside it**, and anything in it but the database forfeits the verdict (files and empty directories). Revert: `_make_sandbox`/`_require_only_the_store_wrote` in `sqlite_runner.py`.
- **`shadow-table` joins the zoo** as the packaged false pass of the night; fifteen sibling shapes are tests, not fixtures.
- **PR #3 closed** (captures are regenerated from tapes at every engine change). Revert: reopen.
- **Two attribution channels are documented, not claimed** (a flag the store's next commit overwrites; the sidecar names). Revert: none, it is prose; closing them means reading the sidecars between store commits, which DECISIONS leaves for a day with a reason.
- **Two PR bodies name a follow-up pin bump** (see hands).

## Needs your hands
1. Merge in the order above, each with "delete branch".
2. `gh pr edit … --base main` is NOT needed: deleting each head branch retargets the next PR.
3. After the last merge: set the action pin in `.github/examples/crashcheck.yml` and STATUS's "reviewed action pin" to the new `main` SHA (one line each; `tests/test_docs_identity.py` refuses drift).
4. Settings → Pages → Build and deployment → Source: GitHub Actions; then Actions → Pages → Run workflow. Only then is there a URL.
5. `set -a; source .env; set +a` with `NEBIUS_API_KEY`, then `docs/LIVE_SETUP.md` Stage A2b (`propose-patch` + `check`) and A2 (`init --nemotron`). Commit the receipts.
6. Actions → Nightly red team → Run workflow (300 cases) once, to see it green on GitHub's Linux.
7. On a quiet laptop: `uv run nemisis benchmark --output benchmarks/results/crashcheck-v1.json` and commit; tonight's timings were taken under load and BENCHMARK says so.

## Alex's ten-minute grading pass
1. `for n in 5 6 7 8 9 10 11 12 13 14; do gh pr view $n --json headRefOid,title -q '.headRefOid+" "+.title'; gh pr checks $n; done` — every head green.
2. `git fetch origin && git checkout overnight2/docs-and-evidence && uv sync --frozen --dev && uv run pytest -q` → 453 passed (2:30 on this laptop).
3. `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/mark-first` → `PATCH_FAILED_INVARIANT_BROKEN`, exit 1.
4. `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/raw-sql` → `EVIDENCE_INCOMPLETE` and the sentence with `store.credit_and_mark(...)`, exit 2.
5. `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/shadow-table` → `EVIDENCE_INCOMPLETE`, "the schema changed", exit 2. This one was `FIX_PROVEN` at 03:00.
6. `uv run nemisis check --base fixture:sqlite-inventory-v1/buggy --candidate fixture:sqlite-inventory-v1/misleading-green` → `timeline: 8 units durable -> SIGKILL -> fresh worker -> 6 units`, exit 1.
7. `open .nemisis/runs/$(ls -t .nemisis/runs | head -1)/report.html` — "Expected stock after one delivery: 8 units" vs "6 units".
8. `uv run nemisis redteam --cases 30 --seed 3 --out ./redteam` → "0 disagreements", exit 0.
9. `git diff 4db4213..overnight2/docs-and-evidence -- src | grep -nE "^\+.*(sleep|xfail|skip\(|timeout=|LIVE)"` → exactly two added lines, both `sqlite3.connect(…, timeout=5)` on read-only probe connections; no sleep, no xfail, no skip, no relabeling.
10. Read the README H1, then row 9 and row 13 of the ledger.

## What I would do next
1. Put the attribution ops into the generator's grammar (extra table, pragma, `..` file, `~` file) and add an inventory grammar; then the nightly sweep covers the shapes that fooled this engine.
2. Run Stage A2b with a key: the `LIVE` Nemotron patch is the demo beat and the last dismissal left.
3. The ConTree transport for CrashCheck (K), designed first in DECISIONS: spawn, subprocess result, process-group kill inside a Sandbox, and what the kernel cannot get from the provider.
