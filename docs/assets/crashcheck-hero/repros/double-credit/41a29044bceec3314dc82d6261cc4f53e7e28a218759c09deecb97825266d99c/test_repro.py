"""Nemisis integration/fault regression.

Capsule: 41a29044bceec3314dc82d6261cc4f53e7e28a218759c09deecb97825266d99c
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
