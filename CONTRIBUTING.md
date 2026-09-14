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

Run all five before every commit. CI runs the same commands on CPython 3.12, 3.13, and 3.14,
plus the composite action and an installed-wheel smoke test.

## Two files the tests keep honest

- `docs/STATUS.md` and `docs/PROOF.md` quote the current engine code digest. It hashes the files
  listed in `_ENGINE_RESOURCES` in `src/nemisis/crashcheck.py`, so an edit to any of those files
  changes it and `tests/test_docs_identity.py` fails until both docs are updated. Print the
  new value with `uv run python -c "from nemisis.crashcheck import engine_code_digest; print(engine_code_digest())"`.
- `docs/STATUS.md` and `docs/PROOF.md` quote the test count. `tests/test_readme_truth.py` fails
  when it drifts from `pytest --collect-only`.

## Red-teaming the checker

`uv run nemisis redteam --cases 100 --seed 1 --out ./redteam` renders a hundred handlers from a
grammar over store operations and the writes around the store that hostile reviews have written
by hand (`Op` in `src/nemisis/redteam.py` is the whole list), runs `check` on each, and compares
the verdict with an oracle computed from the operation sequence alone; `--scenario
sqlite-inventory-v1` speaks the second scenario's vocabulary. It exits `1` on any disagreement and
leaves every handler and its evidence under `./redteam`. A disagreement is either a checker false
pass or false fail or an oracle bug; either is worth an issue with the case's ops and summary. A
new hostile shape belongs in the grammar as an `Op` with its oracle rule, so the nightly sweep
keeps writing it.

## Adding a candidate to the zoo

Pick the scenario first. For `sqlite-credit-v1`, drop a tree under
`src/nemisis/fixtures/sqlite_credit_v1/trees/<name>/app/credits.py`, add the variant to
`ZOO_VARIANTS` and its tree digest to `TREE_DIGESTS` in `src/nemisis/scenarios/sqlite_credit_v1.py`,
and assert the verdict it earns in `tests/test_verdict_paths.py`. For `sqlite-inventory-v1` the same
three steps run through `src/nemisis/fixtures/sqlite_inventory_v1/trees/<name>/app/inventory.py`,
`src/nemisis/scenarios/sqlite_inventory_v1.py`, and `tests/test_inventory_scenario.py`. Both
scenario modules are trusted engine resources, so registering a variant moves the engine code digest
and both ledgers have to be requoted. A candidate that earns `FIX_PROVEN_FOR_THIS_CAPSULE` while being
wrong is the most valuable contribution possible; please open it as an issue even if you cannot
fix the checker.

## The example's action pin

`.github/examples/crashcheck.yml` pins the Nemisis action to one full `main` commit, and
`docs/STATUS.md` names the same SHA as the reviewed action pin. `tests/test_docs_identity.py`
requires the two to agree, requires the pinned commit to be in the current history, and, on
`main`, requires `src/nemisis`, `action.yml`, `pyproject.toml`, and `uv.lock` at that commit to be
byte-identical to `main`'s, so `main` goes red the moment any of them changes without the pin
following. A pull request that changes any of those files ends with one commit that moves both
lines to its last such commit (that commit is in the pull request's history, so the test is green
on the branch and on `main` after the merge). `.github/workflows/pin-bump.yml` is the backstop:
after a push to `main` that changed what the action runs without moving the pin, it opens the
bump itself, with auto-merge, once the repository setting "Allow GitHub Actions to create and
approve pull requests" is on. Never move the pin to a commit that is not in `main`'s history.

## Truth labels

`LOCAL`, `FIXTURE`, `MOCKED`, `BLOCKED`, and `LIVE` are not interchangeable. A pull request that
relabels evidence, fabricates a receipt or digest, or adds a live-to-local fallback will not be
merged regardless of how good the demo looks.
