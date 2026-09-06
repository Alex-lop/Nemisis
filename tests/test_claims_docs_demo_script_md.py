"""Guards for the claims in docs/DEMO_SCRIPT.md."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from nemisis.crash_fixture import MARK_FIRST_REF, materialize_fixture


def test_mark_first_packaged_unit_test_is_green(tmp_path: Path) -> None:
    """The 2:20 beat says the mark-first patch passes the unit test. Nothing else runs it."""
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
