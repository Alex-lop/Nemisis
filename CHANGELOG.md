# Changelog

Every entry is one idea taken from the commit history. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — Unreleased

A second scenario, an adversarial generator that red-teams the checker nightly, and the release
plumbing. Unreleased until a `v0.2.0` tag is pushed.

### Added

- `sqlite-inventory-v1`: a second audited scenario, a decrement with its own seed and its own
  predicate, running on the same kernel as the credit scenario.
- `nemisis redteam`: a grammar over store operations and the writes around the store, an oracle
  computed from the operation sequence alone, and a non-zero exit on any disagreement. The grammar
  speaks the hostile shapes two reviews wrote by hand, in both scenarios.
- A nightly workflow that sweeps generated handlers past the checker, one sweep per audited
  scenario, and uploads every handler and its evidence when the oracle disagrees.
- `raw-sql` in the candidate zoo: a handler that is correct but unjudgeable, told the one-line
  change that makes it judgeable instead of being failed.
- A landing page at the repository root and a Pages workflow that stages the evidence viewer with
  the relative layout it was recorded against.
- A release workflow on `v*` tags: one build, attached to a GitHub release with this file's
  section as its notes, and published to PyPI through a Trusted Publisher with no API token.
- An on-demand `evidence` workflow that reruns the hero check and the benchmark on a Linux runner
  and prints every digest, so the Darwin-measured numbers can be compared against another machine.
- A `Dockerfile` and `.dockerignore`, so a judge with Docker and no uv can build the image and run
  one check without touching their own machine.

### Changed

- One `Scenario` object owns every scenario-specific point, and receipts carry four generic fields
  with the capsule carrying its own event. Neither refactor changed behavior.
- The composite action reports `verdict`, `summary`, and `manifest-path` as outputs, and writes one
  GitHub annotation on the handler file so the verdict is visible outside the log.
- CI runs the whole gate on CPython 3.12, 3.13, and 3.14, and the verify job is bounded at 30
  minutes.
- Pages deploys only when the repository's Pages source is a workflow, so a branch publisher and
  this workflow can never write the same URL.
- The published sdist contains the package, its README, its licence, and its metadata — not a copy
  of the repository.
- The package declares its trove classifiers: alpha, Apache-2.0, POSIX, and 3.12 through 3.14.

### Fixed

- Attribution is the whole database and the whole world the worker runs in, not the rows the
  scenario happens to name.
- The side channels a second hostile review found are closed, and a run refuses a split schedule.
- The read-only probe connection is closed, and the journal-mode flag is pinned by the real failure
  that motivates it.
- The example workflow is pinned to the reviewed `main` commit, and a test fails if that pin drifts
  from the one the status ledger names.

## [0.1.0] — 2026-09-05

The first working vertical slice. Never tagged and never published to PyPI.

### Added

- `nemisis verify`: differential verification of a fixture against its recorded evidence.
- `nemisis check`: the CrashCheck crash/retry proof — kill the worker at a store commit, replay the
  identical event in a fresh process, and probe durable state independently of the handler.
- Irreducible crash schedules: the selected schedule's sole fault action is deleted and fresh
  no-fault worlds must finish exactly once before the crash is blamed.
- A commit sweep that kills after every store commit a claimed fix makes, not only the base's
  boundary.
- Content-addressed repro capsules, run manifests, a standalone HTML report, and a static
  fail-closed evidence viewer.
- `nemisis init` drafts the contract through Nemotron candidate-blind, and the proposal travels into
  the check evidence.
- Nemotron as the coding agent whose patch CrashCheck then judges.
- The candidate zoo as fixture refs, and `nemisis export` to copy a packaged tree you can edit.
- `nemisis benchmark`, its committed result, and the composite GitHub Action.

### Fixed

- A complete run that is not exactly-once is a failed patch, not missing evidence.
- Durable changes the trusted store never reported are refused.
- Receipts are validated relationally, worker output is drained, and cleanup no longer masks a
  failure.
- Worlds are indistinguishable from inside the worker, floods are judged rather than ignored, and
  every error is named.
- One delivery must already be exactly once, and files written beside the database forfeit the
  verdict.
- The `__builtins__` bypass in the patch author is closed, and a tree cannot claim its own author.

### Security

- Contract truth labels are pinned and forks are refused on replay.
- The Token Factory and ConTree adapters are hardened offline.
