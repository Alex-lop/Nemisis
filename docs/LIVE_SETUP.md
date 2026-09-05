# Live setup: from a Token Factory key to a genuine `LIVE` receipt

This is the turnkey path. Everything in the repository that touches a provider is already wired and
tested; the only thing missing in the development environment is the credential. Follow the stages
in order. Each stage says exactly what a success looks like and exactly what a failure looks like,
so nothing has to be interpreted.

Two rules that never bend:

- Nothing is labelled `LIVE` unless a real Token Factory call produced it. Injected clients are
  `MOCKED`; the packaged evidence is `FIXTURE`. The labels are checked by code, not by hand.
- Nothing ever falls back from live to local. A blocked live run exits `2` and records no
  observations: `verify --mode live` writes nothing, and `check --mode live` writes only an
  `EVIDENCE_INCOMPLETE` manifest and report whose observations are absent.

## What you need

| Variable | Needed for | Where it comes from |
| --- | --- | --- |
| `NEBIUS_API_KEY` | `init --nemotron` (Stage A) and `verify --mode live` (Stage B) | Sign in to Nebius Token Factory and create an API key. The official [quickstart](https://docs.tokenfactory.nebius.com/quickstart) shows the current console path and confirms the `NEBIUS_API_KEY` name. |
| `CONTREE_PROFILE`, or an active profile in `~/.config/contree/auth.ini` | Stage B only | Created by the official ConTree client login. Stage A does not need it. |
| `NEMISIS_CONTREE_ROOT_IMAGE` | Stage B only | An immutable Sandbox image **UUID** (never a tag) that provides `/bin/sh`, `/bin/tar`, `/usr/bin/env`, `python` with `pytest`, and `git`. See the [live runbook](LIVE_RUNBOOK.md#immutable-root-image-contract). |
| `NEMISIS_TOKEN_FACTORY_BASE_URL` (optional) | Endpoint override | Defaults to `https://api.tokenfactory.nebius.com/v1/`. Any override must be an official Nebius global or regional HTTPS `/v1` endpoint; anything else is refused before a request is sent. |
| `NEMISIS_MODEL_ID` (optional) | Model override | Defaults to `nvidia/nemotron-3-super-120b-a12b`. The model must be active, `text->text`, and structured-output capable in your authenticated catalog, or the call fails closed. |

Put the values in `.env` (it is gitignored; `.env.example` lists the names) and load them into the
shell before running anything:

```bash
set -a; source .env; set +a
```

The CLI reads environment variables only. It never reads `.env` itself, never writes a credential
anywhere, and never echoes one.

## Stage A: the CrashCheck `LIVE` receipt (needs only the key)

### A1. Confirm the key is visible

```bash
uv run nemisis doctor --mode live
```

Success looks like this. The header still says `BLOCKED` and the exit code is still `2`, because
the three other gates are independent of the key. That is expected at this stage, not a failure:

```text
NEMISIS DOCTOR — LIVE BLOCKED
PASS    python: Python 3.12
PASS    posix-sigkill: process groups and SIGKILL
PASS    sqlite-wal-full: SQLite 3.53.1
PASS    nebius-credential: NEBIUS_API_KEY
BLOCKED contree-profile: ConTree auth profile
BLOCKED immutable-root-image: NEMISIS_CONTREE_ROOT_IMAGE UUID
BLOCKED crashcheck-provider-transport: CrashCheck live provider transport is not implemented
```

Failure looks like `BLOCKED nebius-credential: NEBIUS_API_KEY`. The variable is not exported in
this shell. Fix the shell, not the code. `doctor` only checks presence; it does not authenticate.

### A2. Ask Nemotron for the candidate-blind contract proposal

```bash
rm -f .nemisis/config.json .nemisis/proposal.json   # only if an earlier init left them behind
uv run nemisis init --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --target app.credits:apply_credit --base fixture:sqlite-credit-v1/buggy \
  --scenario sqlite-credit-v1 --nemotron
```

This is one bounded structured-output request. The model sees the issue text and the base handler
only. It never sees a candidate, and it cannot touch the verdict.

Success is exit `0` and six lines. The `LIVE` on the `nemotron:` line is the whole point:

```text
config: /path/to/Nemisis/.nemisis/config.json
contract: a7dda9b1726fc74de0b594c57d3ce2647c21e4e4231431d78f22c92a466f562a
status: ACCEPTED
proposal: /path/to/Nemisis/.nemisis/proposal.json
nemotron: nvidia/nemotron-3-super-120b-a12b · global · LIVE · schema valid · <latency> ms · receipt <64 hex digits>
proposed: nvidia/nemotron-3-super-120b-a12b (LIVE) selected fault intent first-credit-effect-commit-v1; amount_cents=2500 matches the audited event; <k>/<n> catalog IDs; accepted by deterministic catalog check
```

`global` is the endpoint region for the default URL; a regional override prints its region instead.
The `receipt` digest is the value to record in `docs/STATUS.md`.

The failures you can see, and what each one means:

| Output | Meaning | What to do |
| --- | --- | --- |
| `ERROR: NEMOTRON PROPOSAL REJECTED: NEBIUS_API_KEY is required for live Nemotron calls. No contract was drafted.` (exit `2`) | Key not exported in this shell. | Go back to A1. |
| `ERROR: NEMOTRON PROPOSAL REJECTED: nvidia/nemotron-3-super-120b-a12b (LIVE) omitted fault intent first-credit-effect-commit-v1; …` or `… amount_cents=<x> differs from the audited 2500; …` (exit `2`) | The call was real, but the model's proposal did not match the audited scenario, so deterministic code refused to draft. Nothing was written. | Rerun once. If it repeats, keep the output: a refusal is a legitimate demo beat ("the model proposes; it never decides"). Continue with plain `init` (drop `--nemotron`) to demo the rest. |
| An error naming the model or catalog | The configured model is not active or not structured-output capable in your catalog. | Check `NEMISIS_MODEL_ID` against the [catalog probe](LIVE_RUNBOOK.md#2-authenticated-modelcatalog-probe). |
| An error naming the base URL | The override is not an official Nebius HTTPS `/v1` endpoint. | Unset `NEMISIS_TOKEN_FACTORY_BASE_URL` or use the global default. |

Two facts about the receipt: `.nemisis/proposal.json` contains the model ID, region, truth label,
latency, and digests of the prompt, input, and response. It contains no key, no issue text, no
handler source, and no raw model output. You can commit it.

### A3. Carry the receipt into a real CrashCheck run

```bash
uv run nemisis check --base fixture:sqlite-credit-v1/buggy \
  --candidate fixture:sqlite-credit-v1/misleading-green \
  --corrected fixture:sqlite-credit-v1/atomic \
  --scenario .nemisis/config.json --mode local
```

The verdict is unchanged by the proposal, and must be: `verdict: PATCH_FAILED_STILL_REPRODUCES`,
exit `1`. What changes is provenance. The printed `report:` page now has a card titled
**Contract proposal · LIVE Nemotron receipt**, and the manifest carries the same receipt:

```bash
uv run python -c "import json,glob; m=json.load(open(sorted(glob.glob('.nemisis/runs/local-*/manifest.json'))[-1])); print(((m.get('contract_proposal') or {}).get('model_call') or {}).get('truth_label', 'ABSENT'))"
```

That prints `LIVE`. If it prints `MOCKED`, the run used an injected client and is not a live
claim. If it prints `ABSENT`, the run carried no proposal (the manifest's `contract_proposal` is
`null`), which is what every `check` without `--scenario .nemisis/config.json` produces.

### A4. Record it

1. Commit `.nemisis/config.json` and `.nemisis/proposal.json` (both are deliberately excluded
   from `.gitignore`). Do not commit `.env`.
2. In `docs/STATUS.md`, replace the sentence that says `NEBIUS_API_KEY` is absent with the receipt
   digest from the `nemotron:` line and the commit SHA the command ran at.
3. In `docs/PROOF.md`, flip the `Nemotron contract proposal` row from `MOCKED` / `BLOCKED` to
   `LIVE`, quoting the same digest, and remove "Token Factory key" from the missing items in the
   `Genuine current-tree live proof` row (it stays `BLOCKED` on the ConTree profile, the image, and
   the CrashCheck transport). Leave every other row alone.

Stage A is complete when those three things are true. It proves a genuine current-tree Nemotron
call. It does not prove a Sandbox run; that is Stage B.

## Stage B: the differential verifier under a Sandbox (needs all three)

Only the packaged `idempotency-retry` differential verifier is connected to ConTree end to end.
CrashCheck's own `--mode live` transport is not implemented and stays `BLOCKED` by design, even with
every credential present. Do not expect `check --mode live` to produce evidence; it exits `2` with
`EVIDENCE_INCOMPLETE` and does not substitute local execution.

### B1. Confirm all three gates

```bash
uv run nemisis doctor --mode live
```

Success: `nebius-credential`, `contree-profile`, and `immutable-root-image` all read `PASS`. The
header still reads `BLOCKED` and exit is still `2`, solely because of the last line,
`crashcheck-provider-transport`. That line cannot pass in this tree; it is the honest boundary.

Before spending Sandbox resources, run the two authenticated probes in the
[live runbook](LIVE_RUNBOOK.md#probes). They print identities only, never the profile token.

### B2. Run the live verifier

```bash
uv run nemisis verify --fixture idempotency-retry --mode live
```

Success begins `NEMISIS — LIVE` (not `LOCAL FIXTURE`), prints the four-row matrix, and names a
`manifest:` and `report:` under `.nemisis/runs/live-…/`. The expected matrix is the same as local:
three `SUPPORTED` rows and one `UNRESOLVED` crash-retry row, `artifact: REJECTED`. Networking is
disabled inside the guest; the JUnit evidence is guest-produced and returned through bounded output,
which the report says in as many words.

Failure is one of:

- `ERROR: LIVE BLOCKED: <the missing prerequisites>. Local mode was not substituted.` (exit `2`)
- a sanitized ConTree error naming the operation that failed, with no token in it.

In both cases no live manifest is written. Keep the successful `manifest.json` and `report.html`
with the commit SHA; they are the differential path's first `LIVE` receipt.

## What is still not live after both stages

The CrashCheck kill/replay kernel itself runs locally. Running it inside a Sandbox (spawn a worker,
read its subprocess result, kill its process group) is the next engineering milestone, tracked in
`docs/STATUS.md`. Until that code exists and a real run backs it, `doctor --mode live` keeps its
last `BLOCKED` line and the CrashCheck verdicts stay `LOCAL`.
