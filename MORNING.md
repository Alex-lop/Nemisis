# Morning

Branch `overnight/hardening`, 13 commits, pushed. `main` untouched. Gate green at 348 tests on
every commit that is on the remote. Read the log top to bottom; each commit is one idea.

## What is different

1. **The checker got fooled, then fixed.** I wrote candidates to beat it and then ran a 30-agent
   adversarial sweep against the frozen baseline. Two real false passes at `aa1b850`:
   - `mark_processed` then `credit`: PROVEN. Killed between the two, the retry sees the marker and
     never credits. $25 lost, exit 0.
   - The credit written through the handler's own `sqlite3` connection, then `store.mark_processed`:
     PROVEN. The controller only sees store commits, so the real window was never killed.
   Fixes: every claimed fix is now killed once after **each** store commit it makes (a census
   delivery counts them first), and every durable change must match the store operation the
   worker reported. Both handlers now fail with a summary naming the commit and the money.
2. **Complete-but-wrong is a failed patch, not missing evidence.** `PATCH_FAILED_INVARIANT_BROKEN`
   (exit 1) for lost/tripled money. A `$50` result with no marker used to be `EVIDENCE_INCOMPLETE`.
3. **Receipts validate relationally.** Real duplicated-money evidence used to be rejected by a
   fixture-shaped validator and reported as "orchestration failed (ValidationError)". Gone.
4. **Nemotron has a load-bearing job.** `nemisis propose-patch` makes the model the coding agent:
   bug report + buggy module + store API in, whole module out, checker-blind. AST-checked, written
   as an ordinary candidate, crash-tested like anyone's patch, named as author in the report.
5. **Three red-team handlers are packaged fixtures** (`mark-first`, `leftover-credit`,
   `never-marks`), one flag each. README has the table.
6. **Harness bugs a Tuesday-afternoon user would hit:** chatty handlers no longer time out on a full
   pipe; a relative `audit.log` no longer dirties the bound tree (worker cwd moved); cleanup errors
   no longer hide the real failure; split worlds are named ("3 DUPLICATE, 2 EXACTLY_ONCE") not
   averaged; zero-commit and never-credits handlers get actionable messages.
7. **README rewritten** (counterexample first, one command, zoo table, Nemotron beat). Root
   `SECURITY.md` and `CONTRIBUTING.md`. GitHub description and 10 topics set. Hero, benchmark,
   GIF, stills, and viewer captures all regenerated at the final engine.
8. **"Necessity proof" renamed to what it is**, a no-crash control, everywhere a human reads.

## The three dismissals

- **"One hardcoded fixture, can't point it at my code."** Half dead. Any handler body works
  inside the `(store, event)` + `CreditStore` shape, and the zoo proves the checker discriminates
  between bodies. A second scenario is **not** built. The seam does not exist yet: schema, store
  class, seed, probe, and the final-state rule are hardcoded in `sqlite_credit.py` and
  `crash_models.py` (`CreditSnapshot`, `classify_final`, `_STORE_DELTAS`, `_SCHEMA`). I chose
  depth (sweep every commit) over width; I think that was right, and I would say so to a judge.
- **"You wrote the bug, the fix, and the checker."** Mostly dead. Thirty handlers I did not
  hand-pick fooled it or tried to, three are packaged, and Nemotron can author the candidate. What
  is missing is a `LIVE` Nemotron-written patch; that needs the key.
- **"NVIDIA integration is mocked."** Honest, not dead. Two model paths are wired and tested
  (`propose-patch`, `init --nemotron`), one env var switches them on, receipts label `MOCKED` vs
  `LIVE` by code. No `NEBIUS_API_KEY` exists on this machine, so no `LIVE` receipt exists. The
  CrashCheck Sandbox transport is still `BLOCKED`.

## Decisions I made for you

- **No package/repo rename.** Too invasive for one night (install URL, action pin, `.nemisis/`
  paths). I removed the "spelling is intentional" sentence. To rename later: `git mv src/nemisis
  src/nemesis`, `sed -i '' 's/nemisis/nemesis/g; s/Nemisis/Nemesis/g'` over `src tests docs
  pyproject.toml action.yml .github README.md`, rename `.nemisis/` in `crashcheck.py`
  (`CONFIG_PATH`, `AUTHOR_RECEIPT_PATH`, `_IGNORED`), regenerate hero/benchmark, rename the GitHub
  repo (old URL redirects). Half a day with the gate.
- **GitHub description and topics changed** via `gh repo edit`. Revert: `gh repo edit
  Alex-lop/Nemisis --description "..."` and `--remove-topic`.
- **Kept five worlds.** They mean "unanimity or nothing": any disagreement is
  `EVIDENCE_INCOMPLETE`, and the canary test showed why. Documented instead of shrunk.
- **Kept `MinimizationReceipt` field names** in JSON; only prose/CLI/report say "no-crash
  control". Renaming fields is mechanical if you want it.
- **Hero test no longer re-validates evidence from a foreign engine** with live pydantic models
  (structural checks only). Otherwise every model change forced a two-commit hero regen. The hero
  is regenerated at the final engine, so the strict path is active right now.
- **Two local commits were red when first made and were amended before push** (a gate script bug
  swallowed a failing exit code twice). Nothing on the remote was ever rewritten.
- **The imgbot PR #3** is untouched; it would now conflict with the re-recorded PNGs.

## What I tried that did not work

- Finding the "Nemisis" image. Not in the repo, any branch, history, `~/Downloads`, `~/Desktop`,
  or Spotlight. I did not substitute anything. The README has no logo.
- A generic scenario seam. I mapped it and stopped: the receipt validators, capsule fields, CLI
  money formatting, report, benchmark, and viewer all assume credits. Doing it honestly is the
  next multi-hour job, not a 2 AM one.

## What is still weak

- **Nothing is `LIVE`.** Stage A in `docs/LIVE_SETUP.md` is the exact fix; `propose-patch` is the
  beat to record.
- **Local mode is not a sandbox.** A handler that `setsid`s a child which writes after the final
  probe still passes (documented boundary; the red team hit it). ConTree is the answer.
- **Non-store writes cannot be crash-tested at all.** The textbook fix as one direct-SQL
  transaction gets `EVIDENCE_INCOMPLETE` with a clear message, not a pass. A judge who writes
  their own atomic SQL will see this in minute one.
- **A never-credits handler** is `EVIDENCE_INCOMPLETE`, not a failing verdict, because the
  boundary is never reached. Census-first would fix it; I left the note in the code path.
- **The `.claude/worktrees/` entry in `.gitignore`** and the untracked directive `.md` files at the
  root are yours to keep or delete.

## First thing to do

1. `git log --oneline origin/main..overnight/hardening`, then run the quickstart and
   `--candidate fixture:sqlite-credit-v1/mark-first`. Two minutes.
2. If it reads right, open a PR from `overnight/hardening` or fast-forward `main`.
3. Get a Token Factory key and run `docs/LIVE_SETUP.md` Stage A2b (`propose-patch`). That single
   receipt turns the weakest dismissal into the best demo beat.
