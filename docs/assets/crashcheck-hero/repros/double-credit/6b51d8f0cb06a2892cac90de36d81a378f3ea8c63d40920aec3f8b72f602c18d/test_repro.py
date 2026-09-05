"""Nemisis integration/fault regression.

Capsule: 6b51d8f0cb06a2892cac90de36d81a378f3ea8c63d40920aec3f8b72f602c18d
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
