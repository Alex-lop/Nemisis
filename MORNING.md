# Morning

An AI coding agent, handed a repository with a retry bug and nothing but the Nemisis MCP server, a
skill, and one instruction, reached `FIX_PROVEN_FOR_THIS_CAPSULE` with no human input — it listed the
scenarios, got a port template, wrote a port, mapped the crash windows, refined the port, ran
`check` to `FIX_PROVEN_FOR_THIS_CAPSULE`, and applied the same change to the real handler — 14
turns. The one thing that had to be true by morning is true, and the receipt and the tool log are
committed beside the write-up.

| PR | Title | Head | CI on that head | Merge |
| -- | ----- | ---- | --------------- | ----- |
| #34 | feat(map): a verdict-free crash-window map | `838be04` | [green](https://github.com/Alex-lop/Nemisis/actions/workflows/ci.yml) | **merged** `21a23c4` |
| #35 | feat(mcp): a stdio MCP server for an AI coding agent | `c6abf85` | green | **merged** `3081174` |
| #36 | scenario: sqlite-webhook-idempotency-v1 | `f8eab8d` | green on its branch | **staged, open** — surfaced the false pass below |
| #37 | scenario: sqlite-outbox-v1 | `be1badb` | green on its branch | **staged, open** — the second scenario, per the merge cap |
| this | docs: the agent surface — H1, demo, DECISIONS, BENCH | this branch's head | its CI run | auto-merge armed |

## The evidence ledger

| # | Claim | PR | Status | Proof (command → expected) |
| - | ----- | -- | ------ | -------------------------- |
| 1 | Every MCP tool is contract-tested | #35 | PASS | `uv run pytest -q tests/test_mcp_server.py` → 11 passed: list_scenarios/port_template schemas and FIXTURE label, check FIX_PROVEN + LOCAL label + error shape, map census refusal, doctor status, the two Nemotron tools BLOCKED without a key, and a blocked tool writes nothing |
| 2 | The scripted no-model end-to-end test proves the loop | #35 | PASS | `test_the_scripted_agent_reaches_fix_proven_with_no_model`: list_scenarios → port_template → buggy port (fails) → atomic port (`FIX_PROVEN`, exit 0) → the receipt read back as a resource |
| 3 | An unaided agent reached FIX_PROVEN — credit | – | PASS | a fresh `claude -p` headless session, MCP server + skill only, 14 turns: `list_scenarios → port_template → wrote a port → map → refined → check → FIX_PROVEN` (exit 0); fixed `app/credits.py` to `credit_and_mark`. The receipt (`docs/reports/2026-09-15-agent-demo-credit-capsule.json`) and the distilled tool log (`…-toollog.txt`) are committed; write-up and reproduce commands in `docs/reports/2026-09-15-agent-demo.md` |
| 4 | An unaided agent reached FIX_PROVEN — inventory | – | PARTIAL | same loop on `sqlite-inventory-v1`; reached `FIX_PROVEN`, wrote a receipt, applied `reserve_and_mark`; the headless wrapper was cut before its final summary (low memory), so its transcript ends mid-stream and is not committed. Reported as partial, not quoted |
| 5 | `map` is a command and refuses side-channel trees | #34 | PASS | `uv run nemisis map fixture:sqlite-credit-v1/tail-bytes` and `.../raw-sql` → census `INTEGRITY_ERROR`, the refusal sentence, no windows; `.../mark-first` → two clean windows. `uv run pytest -q tests/test_mapping.py` → 8 passed |
| 6 | map is as strict as check on what it refuses | #34 | PASS | its two-lens review found map skipped `scratch.settle`/`_schedule_split`; fixed, with regression tests for both shapes |
| 7 | A scenario merged and its nightly leg | – | FAIL (by choice) | none merged. Both new scenarios are staged (#36, #37) because #36's 8-lens review surfaced a kernel false pass (below); a third "FIX_PROVEN is trustworthy" scenario should not ship while it is open |
| 8 | Every packaged tree's verdict at the final engine | – | PASS | engine digest `1afdb6ee…` unchanged (map and the server are wrappers). credit/inventory zoo verdicts as pinned: `atomic` FIX_PROVEN, `misleading-green` PATCH_FAILED_STILL_REPRODUCES, `mark-first` PATCH_FAILED_INVARIANT_BROKEN, `raw-sql`/`shadow-table`/`tail-bytes` EVIDENCE_INCOMPLETE |
| 9 | `LIVE` receipt | – | FAIL | `printenv NEBIUS_API_KEY \| wc -c` → 0; `draft_contract`/`propose_patch` and every CrashBench row are `BLOCKED` on one export; nothing is `LIVE` |
| 10 | The race fault is designed | – | PASS | `docs/DECISIONS.md` "What `check --fault race` would need the kernel to say": drives two workers through the `_pause` barrier; the census and world scan survive, the sweep and `_finish_replay` change; it **reopens two shapes**; three days |
| 11 | Gate at the merged engine | #35 | PASS | the six gate commands → 634 passed in 3:55; `uv build` ok; mypy --strict clean over the server |

## Explicit negatives
- **The night's headline finding: a kernel false pass.** #36's eight-lens review found that a handler which commits twice on the store's private `_connection` but reports one `_pause` earns `FIX_PROVEN_FOR_THIS_CAPSULE` while non-atomic. Reproduces on credit and inventory; pre-existing (no engine file changed). It uses the store's private API — the in-process boundary `docs/SECURITY.md` already names — but reads as a green verdict rather than a refusal, which is the claim-above-evidence this repo refuses. The obvious fix (audit at `_pause`'s top) breaks the honest path; I verified that. Written up in `docs/DECISIONS.md` with the reproducing handler and the fix it is owed (refuse a `_pause` not called from a store method), for a dedicated hostile-rounds sprint like the 2026-09-08 tail-bytes fix. **Not patched tonight; not filed as acceptable.**
- **No scenario merged.** Both are green and honest on their own branches; both are staged open with ledgers that name their findings (a `subject_noun` wording bug in webhook; the non-commutative count/digest; the false pass they share). The merge cap allows one, but shipping a third trustworthiness claim over the open false pass was the wrong trade.
- **`propose_patch` writes an author receipt to `.nemisis/agent-patches/` in the working directory** (kernel behavior in `agent_patch`), outside the artifact root the server otherwise confines to. It only fires with a key; documented in the trust boundary rather than changed in a wrapper PR.
- **The install line is not yet real from PyPI.** `uv tool install nemisis` gives 0.2.0, which predates the server; the agent install works from a checkout today. Cut 0.2.1 to make it real (next steps).
- **The inventory demo transcript is truncated** (low memory killed the wrapper); the proof and fix are on disk, the closing narration is not.
- **`NEBIUS_API_KEY` is absent**, so the model tools, the third demo run with `propose_patch` as the fixer, and every CrashBench row are `BLOCKED`.

## Decisions made for you (each revertible)
- **The README H1 is the new sentence** ("the crash-safety proof an AI coding agent attaches to its retry fix"), because the demo proved it. Revert: restore the CrashCheck-proves line; it is one commit.
- **A `FIX_PROVEN` receipt from the server comes with a required port ledger** (in the skill and `AGENTS.md`): which real lines map to which store calls, and what the port does not carry. Revert: drop the ledger clause from the skill; the tool is unaffected.
- **Model tiering is by `NEMISIS_MODEL_ID` passed verbatim** (Super default); no tier-name aliases, and the catalog ids come from the Token Factory listing. Revert: none needed; it is a pass-through.
- **Both scenarios are staged, none merged** (above). Revert: merge #36 or #37 after rebasing and requoting, once the false pass is resolved.

## Needs your hands
1. `export NEBIUS_API_KEY=…` — unlocks `draft_contract`, `propose_patch`, the third demo run, and CrashBench's first rows. The one FAIL in the ledger.
2. Cut `0.2.1` so `uv tool install nemisis` ships the `mcp` server: bump `CHANGELOG.md`/`pyproject`, merge, `git tag -a v0.2.1 && git push origin v0.2.1`, watch `Release`. Then `claude mcp add nemisis -- uvx --from nemisis nemisis mcp` works as the README's short form.
3. The five stale remote branches from the prior run are still there; `git push origin --delete …` (restore SHAs in `docs/reports/2026-09-14-morning.md`). The permission layer declined the deletion again.

## Alex's ten-minute grading pass
1. `git fetch origin && git checkout main && git pull && uv sync --frozen --dev && uv run pytest -q` → 634 passed.
2. Be the customer: in a scratch repo with a buggy handler, `claude mcp add nemisis -- uv run --project $(pwd) nemisis mcp` (from your Nemisis checkout), copy `skills/nemisis/SKILL.md` into `.claude/skills/nemisis/`, then `claude -p "Fix the retry bug and prove it is crash-safe with the nemisis MCP tools."` → it reaches `FIX_PROVEN_FOR_THIS_CAPSULE`.
3. `uv run nemisis map fixture:sqlite-credit-v1/mark-first` → two crash windows, no verdict; `uv run nemisis map fixture:sqlite-credit-v1/tail-bytes` → the census refusal, no map.
4. `uv run pytest -q tests/test_mcp_server.py tests/test_mapping.py` → 19 passed.
5. Read `docs/DECISIONS.md` "A handler that reports two commits as one earns FIX_PROVEN" — the headline finding — then `docs/reports/2026-09-15-agent-demo.md`.
6. `git log --format='%h %s' 21a23c4^..main -- src/nemisis | grep -nE "sleep\(|xfail|skip\(|LIVE"` → nothing; the server and map touch no `_ENGINE_RESOURCES` file, so `engine_code_digest()` is unchanged.

## What I would do next
1. **Fix the false pass**, on its own branch with hostile rounds: refuse a `_pause` that did not originate from a store method (caller-frame check), and pin the split-commit shape. This is the trustworthiness of the whole verdict.
2. **Cut 0.2.1** so the agent install is a single `uvx` line, then rerun the demo from the published wheel and add that as a ledger row.
3. **Merge one scenario** (webhook or outbox) after the false pass is resolved: rebase onto main, fix the `subject_noun` wording at the render site, requote the count and digest.

## The team and the window
| Workstream | Subagents | Produced, as counts | State |
| ---------- | --------: | ------------------- | ----- |
| Pillar 1: map | 1 coordinator + 2 lenses + 6 refuters | mapping.py + the command + 8 tests; the review found 2 false-map holes (scratch escape, split schedule), both fixed | merged #34 |
| Pillar 1: server | coordinator + 2 lenses + 6 refuters | mcp_server.py (8 tools, resources) + 11 tests + the skill + AGENTS.md; the review confirmed 11 findings, all fixed | merged #35 |
| Pillar 1: the demo | 2 headless Claude Code agents (fresh, no memory) | credit: FIX_PROVEN unaided, 14 turns; inventory: FIX_PROVEN, transcript truncated | done |
| Pillar 2: scenarios | 2 owners + 8 lenses + 24 refuters (webhook) | two full scenarios, green on their branches; the webhook review surfaced the kernel false pass and 18 doc/word findings | staged #36, #37 |
| Pillar 3: race | 1 cold designer | the `check --fault race` DECISIONS entry; reopens two shapes; three days | done |
| CrashBench | – | `docs/BENCH.md`: row = scenario × model × engine with a receipt or no row; the harness and the Nebius Serverless Job alternative; three rows named, BLOCKED on the key | done |

Under 250 lines. The prior report is `docs/reports/2026-09-14-morning.md`.
