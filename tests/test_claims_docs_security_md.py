"""Pins for two docs/SECURITY.md sentences nothing else held down.

Both read the installed engine source, so neither runs a world.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import ModuleType

import nemisis.crashcheck as crashcheck_module
import nemisis.sqlite_runner as sqlite_runner_module
from nemisis.crashcheck import check

_ROLE_WORDS = ("base", "candidate", "corrected", "census", "sweep", "kill", "replay")


def _module_source(module: ModuleType) -> str:
    return Path(inspect.getfile(module)).read_text(encoding="utf-8")


def test_the_candidate_is_materialized_only_after_the_base_witness_is_frozen() -> None:
    """docs/SECURITY.md: the candidate is not materialized until the witness is frozen."""
    source = inspect.getsource(check)
    assert source.count("_materialize_source(candidate") == 1
    order = [
        source.index("_hunt_hypotheses("),
        source.index("_minimize_witness("),
        source.index("base_attempts = _execute_confirmations("),
        source.index("_materialize_source(candidate"),
    ]
    assert order == sorted(order)


def test_every_world_and_database_is_named_by_an_opaque_identifier() -> None:
    """docs/SECURITY.md: a handler cannot tell a census delivery from a kill world."""
    tree = ast.parse(_module_source(crashcheck_module))
    keywords = [
        keyword
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg in {"work_dir", "database_id"}
    ]
    assert {ast.unparse(k.value) for k in keywords if k.arg == "database_id"} == {
        "f'db-{uuid.uuid4().hex}'"
    }
    # Four routes to a world path; each one ends in uuid.uuid4().hex.
    assert {ast.unparse(k.value) for k in keywords if k.arg == "work_dir"} == {
        "work_root / uuid.uuid4().hex",
        "census_world",
        "worlds[index - 1]",
        "work_root / world",
    }
    assignments = {
        ast.unparse(node.targets[0]): ast.unparse(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and len(node.targets) == 1
    }
    assert assignments["census_world"] == "work_root / uuid.uuid4().hex"
    assert assignments["world"] == "uuid.uuid4().hex"
    worlds = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_worlds"
    )
    assert ast.unparse(worlds.body[-1]) == (
        "return [work_root / uuid.uuid4().hex for _ in range(count)]"
    )


def test_the_worker_argv_and_environment_carry_no_role_name() -> None:
    """docs/SECURITY.md: the phase stays on the controller, out of the spawned worker's world."""
    tree = ast.parse(_module_source(sqlite_runner_module))
    spawn = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_spawn_worker"
    )
    literals = [
        node.value.lower()
        for node in ast.walk(spawn)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert "nemisis.sqlite_runner" in literals
    assert [text for text in literals if any(word in text for word in _ROLE_WORDS)] == []
    popen = next(
        node
        for node in ast.walk(spawn)
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "subprocess.Popen"
    )
    passed = {node.id for node in ast.walk(popen) if isinstance(node, ast.Name)}
    assert "phase" not in passed
