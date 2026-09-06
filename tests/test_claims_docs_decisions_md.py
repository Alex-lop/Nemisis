"""Sentences in docs/DECISIONS.md that only a check can keep honest."""

from __future__ import annotations

from nemisis.crashcheck import _ENGINE_RESOURCES


def test_the_generator_is_not_a_trusted_engine_resource() -> None:
    """It writes candidates and reads verdicts; it must never enter the engine digest."""
    assert "redteam.py" not in _ENGINE_RESOURCES
