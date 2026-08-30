# Status

- Updated: 2026-08-30 UTC
- Repository: `Alex-lop/Nemisis`, branch `main`
- Remote `main` at build start: `0fbb8b37f6961ea1d0ca87fabdec42b34d0696d1`
- Remote `main` at status authoring: `03b58607add660c9da470488eacd74189c34c6c3`
- Source SHA most recently tested: `03b58607add660c9da470488eacd74189c34c6c3`
- Thesis: exact base/candidate worlds must survive one immutable adversarial bundle before an AI
  patch is trusted.

## Present reality

A user can install the package, run the checked-in differential fixture, inspect its CLI matrix,
and open its JSON/HTML evidence. The plausible candidate is rejected because crash-then-retry is
still `ASSERTION_FAIL` in the candidate world. Local evidence is labelled `FIXTURE`.

The real Token Factory and ConTree adapters are implemented and contract-tested. Current live
status is `BLOCKED`: `NEBIUS_API_KEY`, a ConTree profile, and
`NEMISIS_CONTREE_ROOT_IMAGE` are unavailable. No live call, Sandbox run, receipt, or fallback is
claimed.

The verified local bundle digest is
`70e10c52e50c143b526af020c37aee2ee4bce0da85453bb1470d42736895b725`.
Its exact matrix is two `PASS/PASS` invariants, one `ASSERTION_FAIL/PASS` change witness,
and one unresolved `ASSERTION_FAIL/ASSERTION_FAIL` change witness. The artifact is `REJECTED`.

## Verification commands

```bash
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src tests
uv run pytest
uv build
uv run nemisis verify --fixture idempotency-retry --mode local
```

On the source SHA above: locked sync passed; Ruff format and lint passed; strict mypy passed;
113 tests passed; sdist/wheel build passed; the installed wheel ran from an unrelated Git
repository without claiming that repository's SHA; HTML structure validation passed. Live mode
failed closed without fallback and reported the missing API key, immutable root image, and ConTree
profile. No genuine provider call was possible in this environment.

## Recent pushed milestones

- `ebec6d4aa898cb491908d127aac8bdd37f9ac12c` — runnable differential foundation
- `a32290f238d7df68fde5244a88999bcd5c5177da` — status, architecture, proof, and demo docs
- `fad51dbd2fb615dc7895a34c9ef2eea02f6842ec` — Node 24 checkout action pin
- `03b58607add660c9da470488eacd74189c34c6c3` — mandatory live claims and truth-label binding

## Known limitations

- Only the trusted packaged fixture may run locally.
- The live root image must provide `/bin/sh`, `/bin/tar`, `/usr/bin/env`, `python` and `git` on the
  fixed system `PATH`, plus importable `pytest`; that contract is not yet proven against an account.
- Live JUnit is allowed only for the audited packaged fixture/candidate and constrained generated
  tests. ConTree client 0.3.0 has no provider-owned result stream, so arbitrary repositories remain
  unsupported.
- There is no repair attempt, web server, hosted URL, screenshot, or demo video.
- No finite test bundle establishes formal correctness or general security.

## Next three slices

1. Configure credentials/profile/root image and capture one sanitized current-tree live receipt.
2. Record the live matrix and sub-three-minute demo before changing execution-critical code.
3. Only after that gate, add one bounded repair attempt tied to the exact tested candidate image.
