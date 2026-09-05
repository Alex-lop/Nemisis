# Morning

Branch `overnight/hardening`, pushed, `main` untouched. Gate green on every commit that is on the
remote (ruff, mypy, 364 tests). Read `git log origin/main..overnight/hardening` top to bottom; each
commit is one idea and says why. This file is the two-minute version.

## What is different

1. **The checker was fooled, then fixed, three times over.** I wrote candidates to beat it, ran
   two adversarial rounds (30 agents against the baseline, 25 against the hardened engine), and
   had four hostile reviewers read the night's diff; every finding was verified by an independent
   agent before I acted on it. Real false passes and holes found:
   - `mark_processed` then `credit` was PROVEN. Killed between the two, the retry sees the marker
     and never credits: $25 lost, exit 0.
   - The credit written through the handler's own `sqlite3` connection, then `store.mark_processed`,
     was PROVEN. The controller only saw store commits.
   - A `str` subclass with a lying `__eq__` bound a shadow account into the store's own SQL;
     `mark_processed(None)` committed a NULL marker row.
   - A handler that could tell which world it was in (directory named `census`, nonce named
     `candidate-sweep-1`) behaved atomically only where the sweep was counting.
   - A dedup file written beside the database before the atomic call: a crash window no store
     commit can reach, blessed by the sweep.
   - Attribution watched only this event's rows, so a handler could fund another account through
     its own connection and stay PROVEN.
   - A model-written module could reach `__import__` through `__builtins__[...]`, and the
     authorship receipt lived inside the candidate tree where a PR author could hand-write "LIVE".
   - One undecodable byte on stdout ended the text-mode output drain and hid a detached child
     holding the worker's pipes.
   Fixes: every claimed fix is killed once after **each** store commit it makes (a census delivery
   counts them first, and that single delivery must itself be exactly once); every durable change
   must match the store operation the worker reported and every row outside the event must stay
   as seeded; the store requires exact types and values; worlds are named by opaque ids; files
   written beside the database forfeit the verdict; the AST check rejects every underscore name;
   the authorship receipt lives with the operator, keyed by tree digest; drains read raw bytes.
   Every one of these handlers now fails for the right reason.
2. **Complete-but-wrong is a failed patch, not missing evidence.** `PATCH_FAILED_INVARIANT_BROKEN`
   (exit 1) for lost, tripled, or flooded money. Receipts validate through one shared final-state
   rule, so real duplicated-money evidence is never again rejected as "orchestration failed".
3. **Nemotron has a load-bearing job.** `nemisis propose-patch`: the model is the coding agent. Bug
   report, buggy module, and store API in; whole module out; nothing about how CrashCheck kills or
   judges. AST-checked, written as an ordinary candidate, crash-tested like anyone's patch, named as
   author in the report. `init --nemotron` remains the smaller job.
4. **Three red-team handlers are packaged fixtures** (`mark-first`, `leftover-credit`,
   `never-marks`), one flag each, and `nemisis export` gives anyone an editable tree in one line.
   CI smokes `mark-first` from the built wheel on every push.
5. **Messages a Tuesday-afternoon user would hit are fixed:** chatty handlers no longer time out on
   a full pipe; cleanup errors no longer hide the real failure; split worlds are named
   ("3 DUPLICATE_EFFECT, 2 EXACTLY_ONCE"), never averaged; exception types and the delivery phase
   appear in the message; a handler that never credits is told so, and what its no-crash delivery
   did to the money is reported (not judged).
6. **README rewritten** (counterexample first, one command, the zoo as a table, the Nemotron beat).
   Root `SECURITY.md` and `CONTRIBUTING.md`. GitHub description and topics set. Hero, benchmark,
   GIF, stills, and viewer captures regenerated at the hardened engine.
7. **The "necessity proof" is called a no-crash control** everywhere a human reads.

Fresh clone of the branch: `uv sync` 0.4 s, quickstart 2.8 s, replay proven, `mark-first` fails on
the right kill point, export-and-edit proven, `propose-patch` without a key exits 2 and writes nothing.

## The three dismissals

- **"One hardcoded fixture, can't point it at my code."** Half dead. Any handler body works inside
  the `(store, event)` + `CreditStore` shape, `nemisis export` makes trying one a 30-second job, and
  55 adversarial handlers prove the checker discriminates between bodies. A second scenario is
  **not** built; the seam does not exist yet and the exact hardcoded points are listed in
  `docs/DECISIONS.md` ("Depth before width"). I chose depth. I would defend that to a judge: the core
  claim ("survives a real crash") was false for five handler shapes at midnight and is true now.
- **"You wrote the bug, the fix, and the checker."** Mostly dead. The handlers that broke it were
  written by adversaries, three are packaged, and Nemotron can author the candidate. Missing: a
  `LIVE` Nemotron-written patch, which needs the key.
- **"NVIDIA integration is mocked."** Honest, not dead. Two model paths are wired and tested,
  `NEBIUS_API_KEY` switches them on, receipts carry `MOCKED` or `LIVE` by code. No key exists on
  this machine, so no `LIVE` receipt exists. The Sandbox transport is still `BLOCKED`.

## Decisions I made for you

- **No package or repo rename.** Too invasive for one night (install URL, action pin, `.nemisis/`
  paths). I removed the "spelling is intentional" sentence. Recipe: `git mv src/nemisis
  src/nemesis`; `sed -i '' 's/nemisis/nemesis/g; s/Nemisis/Nemesis/g'` over `src tests docs
  pyproject.toml action.yml .github README.md`; rename the `.nemisis` paths in `crashcheck.py`
  (`CONFIG_PATH`, `AUTHOR_RECEIPTS_DIR`, `_IGNORED`) and `agent_patch.py`; regenerate hero and
  benchmark (`scratchpad/regen.sh` was my script; the steps are in `docs/BENCHMARK.md`); rename the
  GitHub repo (old URL redirects). Half a day with the gate.
- **GitHub description and 10 topics changed** via `gh repo edit`. Revert with the same command.
- **The Nemotron authorship receipt is written to your `.nemisis/agent-patches/<tree digest>.json`**,
  not into the candidate tree, and `check` attaches it only when the bound handler's module digest
  matches. Anything a pull request carries about its own author is ignored.
- **Files written beside the database now forfeit the verdict**, including an innocent audit log.
  The tool cannot tell a log from a dedup journal, so it says it cannot judge either. If you want
  logs allowed, the check is `_require_only_the_store_wrote` in `sqlite_credit.py`; I would not.
- **Kept five worlds.** They mean unanimity or nothing; a nondeterministic handler is reported as a
  split. Documented instead of shrunk.
- **Kept `MinimizationReceipt` field names** in JSON; only prose, CLI, and report say "no-crash
  control". Renaming fields is mechanical.
- **A handler that never credits stays `EVIDENCE_INCOMPLETE`** (the crash test cannot run) with the
  no-crash money reported in the summary. One verifier argued it should be a failing verdict; I
  kept "conclusive requires completed" intact. Your call.
- **Hero test re-validates committed evidence with live models only when the engine digest
  matches**; otherwise structural checks. Without this every model change forced a two-commit regen.
- **Two local commits were red when first made and were amended before push** (a gate script bug
  swallowed a failing exit code twice, then fixed). Nothing on the remote was ever rewritten.
- **The imgbot PR #3** is untouched; it now conflicts with the re-recorded PNGs. Close it.

## What I tried that did not work

- Finding the "Nemisis" image: not in the repo, any branch, history, `~/Downloads`, `~/Desktop`,
  or Spotlight. I did not substitute anything. The README has no logo.
- A generic scenario seam. Mapped, not built. Every receipt validator, capsule field, summary, the
  report, the benchmark, and the viewer assume credits; doing it honestly is the next half day.

## What is still weak

- **Nothing is `LIVE`.** `docs/LIVE_SETUP.md` Stage A2b (`propose-patch`) is the exact fix and the
  best demo beat.
- **The AST allowlist for model-written modules is a blocklist plus an underscore rule.** It held
  against a hostile reviewer after the fix, but a sandbox (ConTree) is the real answer for running
  model-written code, and the docs say so.
- **In-process instrumentation has a floor.** A handler can always detect it is inside CrashCheck
  (the store object is in its hands) and behave; a detached child that writes after the final probe
  still passes. Both documented; ConTree is the answer.
- **Non-store durable state elsewhere on disk** (not beside the database) is invisible; documented.
- **The textbook atomic fix as one direct-SQL transaction** gets `EVIDENCE_INCOMPLETE` with a clear
  message, not a pass. A judge who writes their own SQL sees this in minute one.
- **One scenario.** See above.

## First thing to do

1. `git log --oneline origin/main..overnight/hardening`, then the README quickstart and
   `--candidate fixture:sqlite-credit-v1/mark-first`. Two minutes.
2. If it reads right, open a PR from `overnight/hardening` or fast-forward `main`; close imgbot #3.
3. Get a Token Factory key and run Stage A2b. That single receipt turns the weakest dismissal into
   the strongest beat.
