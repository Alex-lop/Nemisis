# CrashCheck in one page

## One breath

AI coding agents ship retry patches that look green and still double-charge in production: the
existing test passes, a "call it twice" check passes, and the bug only appears when a worker dies
between the credit and the marker that says the credit happened. CrashCheck is a crash-test dummy
for those patches. It runs the handler in a real worker, waits until the `$25` credit is durably on
disk, kills the whole process group with `SIGKILL`, confirms the worker is dead, starts a fresh
worker, and delivers the byte-identical event again. Then it reads the SQLite file through an
independent read-only connection. The agent's patch ends at `$50`; the real fix ends at `$25`. The
verdict comes from the database and the process receipts, never from the model that wrote the
patch, and the crash is frozen into a capsule that the next patch has to beat too.

The 30-second recording of exactly that is
[`docs/assets/screenshots/crashcheck-demo.gif`](assets/screenshots/crashcheck-demo.gif); the
90-second spoken version is [DEMO.md](DEMO.md).

## The 90-second story

A bug report says: "a timeout followed by a retry occasionally credits the same order twice."
A coding agent patches `apply_credit`. Its test passes. A plain "call it twice" check passes too.
The patch (`misleading-green`) keeps the original's check → credit → mark shape and differs from
`buggy` only in how the code is written: a different tree, the same crash window, green tests. That
is the case this tool exists for, because nothing short of executing the crash can tell it apart.

CrashCheck runs the handler in a real worker process, waits until the `$25` credit is durably
committed, sends `SIGKILL` to the whole process group, confirms the worker died, starts a fresh
worker, and delivers the byte-identical event again. Then it reads the SQLite file through an
independent read-only connection.

| Revision | Existing test | Call twice | After a real crash and retry | Visual |
| --- | --- | --- | --- | --- |
| buggy | green | `$25` | **`$50`** | GIF beat 1: `BUG_REPRODUCED` |
| agent's "fixed" patch | green | `$25` | **`$50`** | [`terminal-check-misleading-green.png`](assets/screenshots/terminal-check-misleading-green.png), [`report-patch-failed.png`](assets/screenshots/report-patch-failed.png) |
| atomic fix | green | `$25` | `$25` | [`terminal-replay-atomic-proven.png`](assets/screenshots/terminal-replay-atomic-proven.png), [`report-fix-proven.png`](assets/screenshots/report-fix-proven.png) |

It does this in five fresh worlds per revision, in about two seconds, on a laptop. `check` exits
`1` on the agent's patch; replaying the same capsule against the real fix exits `0`. Everything it observed is written to a manifest, a
static HTML report, and a content-addressed repro capsule you can replay against the next patch.

## Where NVIDIA and Nebius come in

- **Nemotron on Token Factory drafts the contract, candidate-blind.** `nemisis init --nemotron`
  sends the bug report and the base handler to `nvidia/nemotron-3-super-120b-a12b` with a strict
  JSON schema over an audited catalog. The model proposes which fault intent applies and what the
  expected single effect is. Deterministic code accepts the proposal only if it matches the audited
  scenario exactly; otherwise nothing is drafted. The model never sees the candidate and never
  emits the verdict. The sanitized receipt travels into the final report. The path is wired and
  contract-tested; it is labelled `LIVE` only when a real Token Factory call produced the receipt,
  and the exact steps to produce one are in [LIVE_SETUP.md](LIVE_SETUP.md).
- **Token Factory Sandboxes are the isolation story.** Local mode is for a trusted checkout only;
  untrusted pull requests are refused by the GitHub Action until the kill/replay kernel runs inside
  a Sandbox. The differential verifier already has a ConTree path; CrashCheck's Sandbox transport
  is the next milestone and is honestly labelled `BLOCKED` until a real receipt exists.

## Why it is not "an LLM judging an LLM"

Every claim in a CrashCheck result is a receipt: the worker's process id and exit code (`-9`), two
distinct worker nonces, the database state before the crash, after the crash, and after the
replay, the exact source tree digest, and the digest of the engine bytes that ran. Model prose
cannot upgrade a result. Missing or contradictory evidence fails closed as `EVIDENCE_INCOMPLETE`.

## How it differs from differential testing you have seen

Running one test suite against a base and a candidate and reporting which tests actually
discriminate between them is established practice. Meta's just-in-time test generation work
([JiTTest, arXiv 2601.22832](https://arxiv.org/pdf/2601.22832)) generates diff-aware tests and
reports how many of them catch anything, and any base-versus-candidate runner can classify a test
that passes on both sides as non-discriminating. Nemisis's own `verify` command is that idea,
applied to one immutable test bundle bound by digest to both worlds, with per-claim verdicts.

The limit of every such tool is the one it shares with the test suite: it can only observe what a
test exercises. No ordinary test kills the process between two statements, so a differential run
of the packaged `idempotency-retry` fixture (`uv run nemisis verify --fixture idempotency-retry
--mode local`; the matrix is in the README) marks its crash-retry claim `UNRESOLVED` (base fails,
candidate fails, nothing learned) and stops. CrashCheck starts there. It does not run the
repository's tests at all. It drives the real handler to its durable checkpoint, kills it, replays,
and reads durable state; the verdict is a database row count and a process exit code, and the crash
is preserved as a capsule that any later patch must survive.

Killing a process at a durable checkpoint and inspecting what survived is not new either:
crash-consistency and fault-injection testing (Jepsen, ALICE, CrashMonkey and their relatives) have
done it to databases and file systems for years. What is specific here is the packaging: the kill is
aimed at one patch's exact side effect, the base is checked candidate-blind first, the verdict is a
per-patch accept/reject with exit codes a CI gate can use, and the crash is frozen into a
content-addressed capsule that the next patch has to beat. It is deliberately narrow: one audited
scenario, one handler shape, executed rather than inferred.

## What it is not, on purpose

One scenario (`sqlite-credit-v1`), one handler shape, Python 3.12+, SQLite, POSIX `SIGKILL`. It
is not a general fuzzer, not a formal verifier, not a repair generator, and a passing result means
"this exact tree defeated this exact capsule," nothing broader. The narrowness is what makes the
verdict trustworthy.

## The ask

Run the quickstart. Watch the agent's green patch lose `$25`. Then replay the capsule against the
atomic fix and watch it hold. That is the whole product.
