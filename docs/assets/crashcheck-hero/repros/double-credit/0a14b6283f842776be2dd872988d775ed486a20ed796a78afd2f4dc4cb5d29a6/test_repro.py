"""Nemisis integration/fault regression.

Capsule: 0a14b6283f842776be2dd872988d775ed486a20ed796a78afd2f4dc4cb5d29a6
This test requires the trusted Nemisis process-kill runner; it is not a unit test.
"""

import os
from pathlib import Path

from nemisis import CrashVerdict, replay


def test_repro() -> None:
    source = os.environ.get("NEMISIS_REPRO_SOURCE", ".")
    role = os.environ.get("NEMISIS_REPRO_ROLE", "candidate")
    result = replay(Path(__file__).with_name("capsule.json"), source, role=role)
    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
