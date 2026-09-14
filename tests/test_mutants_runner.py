"""The mutation runner counts only a failing test as a kill; a pytest that could not run is an
error, not evidence against the mutant."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("mutants", ROOT / "tools" / "mutants.py")
assert SPEC is not None and SPEC.loader is not None
mutants = importlib.util.module_from_spec(SPEC)
sys.modules["mutants"] = mutants  # dataclasses resolve the module by name
SPEC.loader.exec_module(mutants)


@pytest.mark.parametrize(
    ("returncode", "output", "expected"),
    [
        (0, "9 passed", ("survived", None)),
        (
            1,
            "FAILED tests/test_x.py::test_y - assert\n1 failed",
            ("killed", "tests/test_x.py::test_y"),
        ),
        (1, "no failure line at all", ("error", None)),
        (4, "ERROR: file or directory not found: tests/a.py tests/b.py", ("error", None)),
        (2, "ERROR tests/test_x.py - ImportError", ("error", None)),
    ],
)
def test_only_a_failing_test_is_a_kill(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returncode: int,
    output: str,
    expected: tuple[str, str | None],
) -> None:
    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=returncode, stdout=output, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    status, killed_by, _seconds, _output = mutants._pytest(tmp_path, ["tests/test_x.py"], 1.0)
    assert (status, killed_by) == expected
    assert mutants._machine_noise(status, _output) == (status == "error")
