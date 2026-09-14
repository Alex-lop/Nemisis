"""The adversarial generator: the oracle knows the zoo and the hostile shapes, and the checker
agrees with it in both scenario vocabularies."""

from __future__ import annotations

import ast
import json
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
    Case,
    Expected,
    Op,
    Vocabulary,
    generate,
    oracle,
    render,
    run,
    vocabulary_for,
)
from nemisis.sqlite_runner import WORKER_TIMEOUT_VARIABLE

G, E, M, A = Op.GUARD, Op.EFFECT, Op.MARK, Op.ATOMIC
TM, RE = Op.TRY_MARK, Op.RETRY_EFFECT
F, PF, HF, TF, DF = Op.RAW_FILE, Op.PARENT_FILE, Op.HOME_FILE, Op.TMP_FILE, Op.DELETE_FILE
S, T, P, R, D = Op.RAW_SQL, Op.TABLE, Op.PRAGMA, Op.REPOINT, Op.DETECT
HF, TB, HC, HR = Op.HEADER_FLAG, Op.TAIL_BYTES, Op.HOME_CHMOD, Op.HOME_RMDIR


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
        # The third hostile review's channels: a header field no store commit rewrites, bytes past
        # the last page, the mode of the world's HOME, HOME removed.
        ((HF, A), Expected.INCOMPLETE, "around the store"),
        ((A, TB), Expected.INCOMPLETE, "around the store"),
        ((HC, A), Expected.INCOMPLETE, "around the store"),
        ((A, HR), Expected.INCOMPLETE, "around the store"),
        ((A, G, HC), Expected.PROVEN, "every kill point"),
        # The nightly red team's first real finding (runs 34219859012, 34345065158, 34593382316,
        # 34689225054, 34755449725): bytes past the last page written after the last commit. The
        # oracle was right; the kernel read the file only after the worker's exit had truncated it.
        ((E, TB), Expected.INCOMPLETE, "around the store"),
        ((G, E, TB), Expected.INCOMPLETE, "around the store"),
        ((G, A, TB, G), Expected.INCOMPLETE, "around the store"),
        ((G, A, TB), Expected.INCOMPLETE, "around the store"),
        ((E, TM, TB), Expected.INCOMPLETE, "around the store"),
        ((A, E, TM, TB), Expected.INCOMPLETE, "around the store"),
        ((A, A, E, TB), Expected.INCOMPLETE, "around the store"),
        ((RE, TB), Expected.INCOMPLETE, "around the store"),
        ((RE, A, A, TB, G), Expected.INCOMPLETE, "around the store"),
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
        # The nightly's finding, in the decrement vocabulary: run 34593382316 case 16 was proven.
        ((G, A, TB, G), False, CrashVerdict.EVIDENCE_INCOMPLETE),
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


NIGHTLY_SHAPES = (
    ((E, TB), False),  # runs 34219859012 case 163 and 34593382316 case 25
    ((G, E, TB), False),  # run 34593382316 case 11
    ((G, A, TB, G), False),  # run 34593382316 case 16: FIX_PROVEN_FOR_THIS_CAPSULE
    ((G, A, TB), True),  # run 34593382316 case 87: FIX_PROVEN_FOR_THIS_CAPSULE, via a helper
    ((E, TM, TB), False),  # run 34593382316 case 26
    ((A, E, TM, TB), False),  # run 34345065158 case 211
    ((A, A, E, TB), False),  # run 34755449725 case 11
    ((RE, TB), False),  # run 34689225054 case 142
    ((RE, A, A, TB, G), False),  # run 34219859012 case 97
)


@pytest.mark.parametrize(("ops", "helper"), NIGHTLY_SHAPES, ids=lambda v: str(v))
def test_the_nightly_shapes_agree_with_the_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ops: tuple[Op, ...], helper: bool
) -> None:
    """Every disagreement the nightly red team reported between 2026-09-08 and 2026-09-13, rerun
    in the credit vocabulary: the kernel now says what the oracle says."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    tree = tmp_path / "candidate"
    (tree / "app").mkdir(parents=True)
    (tree / "app" / "__init__.py").write_text('"""generated"""\n', encoding="utf-8")
    (tree / "app" / "credits.py").write_text(render(ops, CREDIT, helper=helper), encoding="utf-8")

    result = check(CREDIT.base_ref, tree, CREDIT.scenario_id, mode="local")

    expected, why = oracle(ops)
    assert expected is Expected.INCOMPLETE, why
    assert result.verdict.value == expected.value, result.summary
    assert "before the worker exited" in result.summary, result.summary


def _case(
    index: int, expected: Expected, verdict: str, summary: str, *, timed_out: bool = False
) -> Case:
    return Case(index, (A,), False, expected, "why", verdict, summary, timed_out)


def test_a_wall_clock_refusal_is_unknown_not_agreement_and_not_disagreement() -> None:
    """The machine, not the handler: a world the kernel ended in TIMEOUT is neither side, and
    the decision is the kernel's execution status, never the summary's text, which quotes names
    the handler chose (a hostile lens named a side file NEMISIS_WORKER_TIMEOUT_SECONDS)."""
    timed_out = _case(
        1,
        Expected.INCOMPLETE,
        CrashVerdict.EVIDENCE_INCOMPLETE.value,
        f"the replay delivery's next store commit did not arrive within 10 s; "
        f"{WORKER_TIMEOUT_VARIABLE} raises the budget on a slow machine",
        timed_out=True,
    )
    assert timed_out.unknown
    assert not timed_out.agrees  # the verdict strings match, and that must not count
    assert not timed_out.disagrees
    laundered = _case(
        4,
        Expected.PROVEN,
        CrashVerdict.EVIDENCE_INCOMPLETE.value,
        "the handler wrote durable entries outside the store "
        f"(sandbox/cwd/{WORKER_TIMEOUT_VARIABLE})",
    )
    assert not laundered.unknown and laundered.disagrees
    real = _case(2, Expected.INCOMPLETE, CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE.value, "proven")
    assert not real.unknown and real.disagrees
    fine = _case(3, Expected.PROVEN, CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE.value, "proven")
    assert not fine.unknown and fine.agrees and not fine.disagrees


def test_the_cli_counts_unknown_apart_and_fails_only_above_the_threshold(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import nemisis.redteam as redteam

    cases = [
        _case(1, Expected.PROVEN, CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE.value, "proven"),
        _case(
            2,
            Expected.PROVEN,
            CrashVerdict.EVIDENCE_INCOMPLETE.value,
            f"the census delivery's hello did not arrive within 10 s; {WORKER_TIMEOUT_VARIABLE} "
            "raises the budget on a slow machine",
            timed_out=True,
        ),
    ]
    monkeypatch.setattr(redteam, "run", lambda *args, **kwargs: cases)

    def main(*extra: str) -> int:
        out = tmp_path / f"rt-{len(extra)}"
        argv = ["nemisis", "redteam", "--cases", "2", "--out", str(out), *extra]
        monkeypatch.setattr(sys, "argv", argv)
        try:
            cli.main()
        except SystemExit as exit_info:
            return int(exit_info.code or 0)
        return 0

    assert main() == 1
    printed = capsys.readouterr().out
    assert (
        "0 disagreements; 1 unknown (the kernel ran out of wall clock; --max-unknown 0)" in printed
    )
    assert "case 2: UNKNOWN, the machine:" in printed
    assert main("--max-unknown", "1") == 0
    assert main("--max-unknown", "1", "--json") == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["unknown"] == 1 and payload["disagreements"] == 0
    assert [case["unknown"] for case in payload["cases"]] == [False, True]
