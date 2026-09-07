"""The adversarial generator: the oracle knows the zoo and the hostile shapes, and the checker
agrees with it in both scenario vocabularies."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

import nemisis.cli as cli
from nemisis.crash_models import CrashVerdict
from nemisis.crashcheck import check
from nemisis.redteam import (
    CREDIT,
    HAZARD_OPS,
    INVENTORY,
    STORE_OPS,
    Expected,
    Op,
    Vocabulary,
    generate,
    oracle,
    render,
    run,
    vocabulary_for,
)

G, E, M, A = Op.GUARD, Op.EFFECT, Op.MARK, Op.ATOMIC
TM, RE = Op.TRY_MARK, Op.RETRY_EFFECT
F, PF, HF, TF, DF = Op.RAW_FILE, Op.PARENT_FILE, Op.HOME_FILE, Op.TMP_FILE, Op.DELETE_FILE
S, T, P, R, D = Op.RAW_SQL, Op.TABLE, Op.PRAGMA, Op.REPOINT, Op.DETECT


@pytest.mark.parametrize(
    ("ops", "expected", "reason"),
    [
        # The packaged zoo, as operation sequences.
        ((G, E, M), Expected.STILL_REPRODUCES, "boundary"),  # buggy / misleading-green
        ((A,), Expected.PROVEN, "every kill point"),  # atomic
        ((G, M, E), Expected.INVARIANT_BROKEN, "sweep"),  # mark-first
        ((A, E), Expected.STILL_REPRODUCES, "boundary"),  # leftover-credit
        ((E,), Expected.STILL_REPRODUCES, "boundary"),  # never-marks
        ((S,), Expected.INCOMPLETE, "around the store"),  # raw-sql
        ((T, A), Expected.INCOMPLETE, "around the store"),  # shadow-table
        # Shapes from the hardening night.
        ((G, A, E), Expected.STILL_REPRODUCES, "census"),  # guarded leftover credit
        ((E, E, M), Expected.INVARIANT_BROKEN, "boundary"),  # over-crediting
        ((M, A), Expected.INCOMPLETE, "never reached"),  # mark then atomic
        ((M,), Expected.INCOMPLETE, "never reached"),
        ((G,), Expected.INCOMPLETE, "never reached"),
        ((S, M), Expected.INCOMPLETE, "around the store"),  # raw credit, store marker
        ((A, S), Expected.INCOMPLETE, "around the store"),  # drift after the last commit
        ((F, A), Expected.INCOMPLETE, "around the store"),  # inflight file
        ((E, M, M), Expected.INCOMPLETE, "raised"),  # a second marker raises on redelivery
        ((M, E), Expected.INCOMPLETE, "raised"),  # unguarded mark-first raises on redelivery
        ((A, A), Expected.PROVEN, "every kill point"),
        ((G, M, E, E), Expected.STILL_REPRODUCES, "census"),
        # Reachability: a raw write is only a write if some world executes it. Case 44 of the
        # first 60-case sweep: the checker was right and the oracle was wrong.
        ((A, G, S, E), Expected.PROVEN, "every kill point"),
        ((A, G, F), Expected.PROVEN, "every kill point"),
        ((G, A, F), Expected.INCOMPLETE, "around the store"),
        ((E, G, S, M), Expected.INCOMPLETE, "around the store"),
        ((G, E, M, F), Expected.INCOMPLETE, "around the store"),
        # The second and third hostile reviews' shapes, now in the grammar.
        ((TM, E), Expected.STILL_REPRODUCES, "boundary"),  # a swallowed second marker duplicates
        ((G, TM, E), Expected.INVARIANT_BROKEN, "sweep"),  # mark-first in a try is still lost
        ((RE, M), Expected.STILL_REPRODUCES, "boundary"),  # a retry loop is one commit
        ((G, RE, TM), Expected.STILL_REPRODUCES, "boundary"),
        ((P, A), Expected.INCOMPLETE, "around the store"),  # user_version flag
        ((A, P), Expected.INCOMPLETE, "around the store"),
        ((R, A), Expected.INCOMPLETE, "around the store"),  # a re-pointed row on the redelivery
        ((A, R), Expected.INCOMPLETE, "around the store"),
        ((R,), Expected.INCOMPLETE, "never reached"),  # nothing to re-point, nothing committed
        ((PF, A), Expected.INCOMPLETE, "around the store"),  # ../side.txt
        ((HF, A), Expected.INCOMPLETE, "around the store"),  # ~/side.txt
        ((TF, A), Expected.INCOMPLETE, "around the store"),  # $TMPDIR/side.txt
        ((A, G, HF), Expected.PROVEN, "every kill point"),  # dead code after the guard
        # A file tidied away before any scan was never durable state at a kill point.
        ((F, DF, A), Expected.PROVEN, "every kill point"),
        ((A, F, DF), Expected.PROVEN, "every kill point"),
        ((F, E, DF, M), Expected.INCOMPLETE, "around the store"),  # present at the kill
        ((PF, DF, A), Expected.INCOMPLETE, "around the store"),  # the delete reaches only cwd
        ((DF,), Expected.INCOMPLETE, "never reached"),
        # World detection must be a no-op: every world is named by an opaque id.
        ((D, A), Expected.PROVEN, "every kill point"),
        ((G, D, E, M), Expected.STILL_REPRODUCES, "boundary"),
        ((D,), Expected.INCOMPLETE, "never reached"),
    ],
)
def test_oracle_knows_the_zoo(ops: tuple[Op, ...], expected: Expected, reason: str) -> None:
    verdict, why = oracle(ops)
    assert verdict is expected, why
    assert reason in why


def test_generation_is_deterministic_and_distinct() -> None:
    first = generate(60, seed=7)
    assert first == generate(60, seed=7)
    assert len(first) == 60 == len(set(first))
    assert generate(60, seed=8) != first
    assert all(1 <= len(shape.ops) <= 6 for shape in first)
    assert any(shape.helper for shape in first)
    assert any(op in HAZARD_OPS for shape in first for op in shape.ops)
    assert all(sum(op in STORE_OPS for op in shape.ops) >= 1 for shape in first)


@pytest.mark.parametrize("vocabulary", [CREDIT, INVENTORY], ids=lambda v: v.scenario_id)
def test_every_op_renders_to_valid_python_in_both_shapes(vocabulary: Vocabulary) -> None:
    for op in Op:
        for helper in (False, True):
            module = ast.parse(render((op,), vocabulary, helper=helper))
            names = [node.name for node in module.body if isinstance(node, ast.FunctionDef)]
            assert names[-1] == vocabulary.function
            assert (names[0] == "_deliver") is helper


def test_render_is_a_bindable_handler() -> None:
    source = render((G, S, M))
    assert source.startswith('"""Generated by nemisis redteam')
    assert "import sqlite3" in source
    assert "def apply_credit(store, event):" in source
    assert "store._database" in source
    assert render(()).endswith("    return\n")
    inventory = render((G, A, T), INVENTORY, helper=True)
    assert "def reserve_inventory(store, event):\n    _deliver(store, event)\n" in inventory
    assert 'store.reserve_and_mark(event["sku"], event["event_id"], event["quantity"])' in inventory
    assert "CREATE TABLE IF NOT EXISTS dedup" in inventory


def test_vocabulary_is_refused_for_an_unknown_scenario(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(ValueError, match="unsupported scenario"):
        vocabulary_for("sqlite-nope-v1")
    argv = ["nemisis", "redteam", "--cases", "1", "--scenario", "sqlite-nope-v1"]
    monkeypatch.setattr(sys, "argv", [*argv, "--out", str(tmp_path / "rt")])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2
    assert "unsupported scenario" in capsys.readouterr().err


def test_ten_generated_handlers_agree_with_the_oracle(tmp_path: Path) -> None:
    """The normal-suite sweep: fixed seed, bounded runtime, zero disagreements."""
    cases = run(10, seed=7, out=tmp_path / "redteam")

    assert len(cases) == 10
    disagreements = [case for case in cases if not case.agrees]
    assert not disagreements, [
        (case.index, case.ops, case.expected, case.verdict, case.summary) for case in disagreements
    ]
    assert len({case.expected for case in cases}) >= 2


@pytest.mark.parametrize(
    ("ops", "helper", "expected"),
    [
        ((G, E, M), False, CrashVerdict.PATCH_FAILED_STILL_REPRODUCES),
        ((A,), True, CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE),
        ((G, TM, E), False, CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN),
        ((D, PF, A), True, CrashVerdict.EVIDENCE_INCOMPLETE),
    ],
)
def test_inventory_vocabulary_agrees_with_the_oracle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ops: tuple[Op, ...],
    helper: bool,
    expected: CrashVerdict,
) -> None:
    """The same oracle judges the decrement scenario; the grammar only changes its spelling."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    tree = tmp_path / "candidate"
    (tree / "app").mkdir(parents=True)
    (tree / "app" / "__init__.py").write_text('"""generated"""\n', encoding="utf-8")
    (tree / "app" / "inventory.py").write_text(
        render(ops, INVENTORY, helper=helper), encoding="utf-8"
    )

    result = check(INVENTORY.base_ref, tree, INVENTORY.scenario_id, mode="local")

    assert oracle(ops)[0].value == expected.value
    assert result.verdict is expected, result.summary
