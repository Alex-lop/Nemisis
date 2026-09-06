# Contributing

Thanks for looking. The bar for a change here is simple: nothing lands unless the whole gate is
green, and nothing in the docs claims more than the code proves.

## The gate

```bash
uv sync --frozen --dev
uv run ruff format --check src tests
uv run ruff check src tests
uv run mypy src tests
uv run pytest
```

Run all four before every commit. CI runs the same commands plus the composite action and an
installed-wheel smoke test.

## Two files the tests keep honest

- `docs/STATUS.md` and `docs/PROOF.md` quote the current engine code digest. Any edit to a trusted
  engine file changes it; `tests/test_docs_identity.py` fails until both docs are updated. Print the
  new value with `uv run python -c "from nemisis.crashcheck import engine_code_digest; print(engine_code_digest())"`.
- `docs/STATUS.md` and `docs/PROOF.md` quote the test count. `tests/test_readme_truth.py` fails
  when it drifts from `pytest --collect-only`.

## Red-teaming the checker

`uv run nemisis redteam --cases 100 --seed 1 --out ./redteam` renders a hundred handlers from a
grammar over store operations, runs `check` on each, and compares the verdict with an oracle
computed from the operation sequence alone. It exits `1` on any disagreement and leaves every
handler and its evidence under `./redteam`. A disagreement is either a checker false pass or false
fail or an oracle bug; either is worth an issue with the case's ops and summary.

## Adding a candidate to the zoo

Drop a tree under `src/nemisis/fixtures/sqlite_credit_v1/trees/<name>/app/credits.py`, register the
variant and its tree digest in `src/nemisis/scenarios/sqlite_credit_v1.py`, and add its expected
verdict to `tests/test_verdict_paths.py`. A candidate that earns `FIX_PROVEN_FOR_THIS_CAPSULE` while being
wrong is the most valuable contribution possible; please open it as an issue even if you cannot
fix the checker.

## Truth labels

`LOCAL`, `FIXTURE`, `MOCKED`, `BLOCKED`, and `LIVE` are not interchangeable. A pull request that
relabels evidence, fabricates a receipt or digest, or adds a live-to-local fallback will not be
merged regardless of how good the demo looks.
