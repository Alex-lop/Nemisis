"""Claims in `docs/PROOF.md` that nothing else in the suite pins."""

from __future__ import annotations

from nemisis.crashcheck import _ENGINE_RESOURCES


def test_the_red_team_generator_is_not_an_engine_resource() -> None:
    """A red-team tool must never move the engine digest that binds committed receipts."""
    assert not any(name.startswith("redteam") for name in _ENGINE_RESOURCES)
