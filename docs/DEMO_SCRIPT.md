# Three-minute demo script

The 90-second cut, with pasted expected output and the screenshots that back each beat, is
[DEMO.md](DEMO.md). This is the longer version with the Nemotron beat and every fallback.

Timed for a live judge or a recording. Left column is what you type, middle is what appears on
screen, right is what you say. Every beat has a fallback so a live failure never becomes dead air.

## Pre-flight (do not skip)

```bash
cd /tmp && rm -rf crashcheck-demo && mkdir crashcheck-demo && cd crashcheck-demo
git clone https://github.com/Alex-lop/Nemisis.git . && uv sync --frozen --dev   # warms the cache
uv run nemisis doctor --mode local                                            # expect READY
export NEBIUS_API_KEY=...                                                     # only if you have it
cp src/nemisis/fixtures/sqlite_credit_v1/issue.md issue.md
clear
```

Terminal at 18pt or larger, 100 columns wide, dark theme, notifications off. Run from `/tmp` so no
home-directory path appears in the recording. Have `docs/PITCH.md` open in a second tab.

## Script

| Time | You type | Judge sees | You say |
| --- | --- | --- | --- |
| 0:00 | (nothing) | Terminal, `issue.md` open beside it | "This bug report says a retry sometimes credits an order twice. An AI agent fixed it. Its test is green. I'm going to crash the process and see if the money is really safe." |
| 0:15 | `sed -n '/^def apply_credit/,$p' src/nemisis/fixtures/sqlite_credit_v1/trees/misleading-green/app/credits.py` | Just the handler: check marker, credit, mark processed | "Here is the agent's rewrite. Looks right: if we've seen the event, return; otherwise credit, then mark. Same shape as the original, and the crash window is still between those last two lines." |
| 0:35 | `uv run nemisis init --issue issue.md --target app.credits:apply_credit --base fixture:sqlite-credit-v1/buggy --scenario sqlite-credit-v1 --nemotron` | `nemotron: nvidia/nemotron-3-super-120b-a12b · global · LIVE · schema valid · … ms · receipt …` then `proposed: … selected fault intent first-credit-effect-commit-v1; amount_cents=2500 matches the audited event` | "First, Nemotron on Nebius Token Factory reads the bug report and the base handler, never the patch, and proposes the contract: which fault, and that one effect should be exactly twenty-five dollars. Our code checks that proposal against the audited catalog. The model proposes; it never decides." |
| 1:00 | `uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate fixture:sqlite-credit-v1/misleading-green --corrected fixture:sqlite-credit-v1/atomic --scenario .nemisis/config.json --mode local` | ~2 s later: `verdict: PATCH_FAILED_STILL_REPRODUCES` and `timeline: $25.00 durable -> SIGKILL -> fresh worker -> $50.00` | "Now the real test. It starts a worker, waits for the twenty-five dollar credit to hit disk, sends SIGKILL to the process group, confirms the worker is dead, starts a brand-new worker, and replays the identical event. Fifty dollars. Five fresh worlds, five times. Exit code one." |
| 1:35 | `open .nemisis/runs/*/report.html` (macOS) or paste the printed `report:` path into a browser | Red hero: **Patch still duplicates the effect**, `$25.00 vs $50.00`; below it the Nemotron contract-proposal card and the five attempt receipts | "This is the artifact a reviewer gets. Expected twenty-five, observed fifty. Here is the model's proposal receipt with the truth label, and here are the process ids, the exit code minus nine, the two worker nonces, the database snapshots. No model confidence anywhere." |
| 2:05 | `uv run nemisis replay .nemisis/repros/double-credit/*/capsule.json --source fixture:sqlite-credit-v1/atomic --role corrected --mode local` | `verdict: FIX_PROVEN_FOR_THIS_CAPSULE`, exit `0` | "Same frozen capsule, same kill, against the atomic fix. Twenty-five dollars, one ledger row, one marker. This is the regression test that ships with the repro: the next patch has to beat the same crash." |
| 2:35 | (nothing) | Report still on screen | "What's proven is narrow on purpose: this exact tree beat this exact capsule. What's next is running that kill inside a Nebius Sandbox so untrusted pull requests can be checked too. Everything you saw is in the manifest, and nothing in it is labelled live unless a real receipt backs it." |
| 2:55 | stop | | |

## Fallbacks

- **No `NEBIUS_API_KEY` on the demo machine.** Run the `init --nemotron` command anyway: it exits
  `2` with `NEMOTRON PROPOSAL REJECTED: NEBIUS_API_KEY is required` and drafts nothing. Say: "Fail
  closed. Without the key there is no model call and no contract." Then run `init` without
  `--nemotron` (the audited fixture contract) and continue; the report will carry no proposal card.
  Do not show a `MOCKED` receipt to a judge as if it were live.
- **Nemotron proposes a mismatch.** The command exits `2` and prints the model's actual values.
  Say: "The model got the amount wrong, so we refused to draft. That is the point." Continue with
  plain `init`.
- **`check` returns `EVIDENCE_INCOMPLETE`.** Read the `summary:` line aloud; it names the missing
  receipt. Fall back to the committed evidence: `uv run python -m http.server 8000 --bind 127.0.0.1` and open
  `http://127.0.0.1:8000/docs/assets/crashcheck-hero/`, click **Replay fixture evidence**. Say
  clearly that this is the committed `LOCAL` / `FIXTURE` receipt bound to an earlier exact commit.
- **Browser will not open.** `uv run nemisis check ... --json | head -c 600` shows the verdict and
  digests; the report is optional.
- **Wrong directory or stale `.nemisis/`.** `rm -rf .nemisis` and rerun from `init`.

## Recording notes

- One take per beat is fine; cut on the `clear`.
- Keep the cursor still while output prints; the `timeline:` line is the money shot.
- If a path with a username shows, re-run from `/tmp/crashcheck-demo`.
- Under three minutes total; the judge may decide from the video alone.
