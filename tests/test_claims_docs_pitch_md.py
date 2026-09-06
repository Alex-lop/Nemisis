"""Claims in `docs/PITCH.md` that nothing else in the suite pins.

PITCH says `mark-first` "passes the unit test". Nothing ran that tree's own test: the benchmark's
green column only measures the three hero trees, and `check` never runs a candidate's suite.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from nemisis.crash_fixture import MARK_FIRST_REF, materialize_fixture


def test_mark_first_passes_the_trees_own_unit_test(tmp_path: Path) -> None:
    tree = materialize_fixture(MARK_FIRST_REF, tmp_path / "mark-first").path

    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
        cwd=tree,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert re.search(r"1 passed", run.stdout), run.stdout
