# CrashCheck in one page

## One breath

AI coding agents ship retry patches that look green and still double-charge in production.
CrashCheck is a crash-test dummy for those patches: it kills the worker after the money moves,
restarts it, replays the same event, and checks the database for a duplicate. The verdict comes
from the database and the process receipts, not from the model that wrote the patch.

## The 90-second story

A bug report says: "a timeout followed by a retry occasionally credits the same order twice."
A coding agent patches `apply_credit`. Its test passes. A plain "call it twice" check passes too.

CrashCheck runs the handler in a real worker process, waits until the `$25` credit is durably
committed, sends `SIGKILL` to the whole process group, confirms the worker died, starts a fresh
worker, and delivers the byte-identical event again. Then it reads the SQLite file through an
independent read-only connection.

| Revision | Existing test | Call twice | After a real crash and retry |
| --- | --- | --- | --- |
| buggy | green | `$25` | **`$50`** |
| agent's "fixed" patch | green | `$25` | **`$50`** |
| atomic fix | green | `$25` | `$25` |

It does this in five fresh worlds per revision, in about two seconds, on a laptop, and exits `1`
for the agent's patch and `0` for the real fix. Everything it observed is written to a manifest, a
static HTML report, and a content-addressed repro capsule you can replay against the next patch.

## Where NVIDIA and Nebius come in

- **Nemotron on Token Factory drafts the contract, candidate-blind.** `nemisis init --nemotron`
  sends the bug report and the base handler to `nvidia/nemotron-3-super-120b-a12b` with a strict
  JSON schema over an audited catalog. The model proposes which fault intent applies and what the
  expected single effect is. Deterministic code accepts the proposal only if it matches the audited
  scenario exactly; otherwise nothing is drafted. The model never sees the candidate and never
  emits the verdict. The sanitized receipt travels into the final report.
- **Token Factory Sandboxes are the isolation story.** Local mode is for a trusted checkout only;
  untrusted pull requests are refused by the GitHub Action until the kill/replay kernel runs inside
  a Sandbox. The differential verifier already has a ConTree path; CrashCheck's Sandbox transport
  is the next milestone and is honestly labelled `BLOCKED` until a real receipt exists.

## Why it is not "an LLM judging an LLM"

Every claim in a CrashCheck result is a receipt: the worker's process id and exit code (`-9`), two
distinct worker nonces, the database state before the crash, after the crash, and after the
replay, the exact source tree digest, and the digest of the engine bytes that ran. Model prose
cannot upgrade a result. Missing or contradictory evidence fails closed as `EVIDENCE_INCOMPLETE`.

## What it is not, on purpose

One scenario (`sqlite-credit-v1`), one handler shape, Python 3.12+, SQLite, POSIX `SIGKILL`. It
is not a general fuzzer, not a formal verifier, not a repair generator, and a passing result means
"this exact tree defeated this exact capsule," nothing broader. The narrowness is what makes the
verdict trustworthy.

## The ask

Run the quickstart. Watch the agent's green patch lose `$25`. Then replay the capsule against the
atomic fix and watch it hold. That is the whole product.
