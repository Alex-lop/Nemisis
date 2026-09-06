"""The audited scenarios CrashCheck can run, keyed by scenario id."""

from __future__ import annotations

from collections.abc import Mapping

from nemisis.scenario import Scenario
from nemisis.scenarios import sqlite_credit_v1, sqlite_inventory_v1

SCENARIOS: Mapping[str, Scenario] = {
    sqlite_credit_v1.SCENARIO.scenario_id: sqlite_credit_v1.SCENARIO,
    sqlite_inventory_v1.SCENARIO.scenario_id: sqlite_inventory_v1.SCENARIO,
}


def scenario_for(scenario_id: object) -> Scenario:
    """The registered scenario, or a ValueError naming the ids that exist."""
    if isinstance(scenario_id, str) and scenario_id in SCENARIOS:
        return SCENARIOS[scenario_id]
    raise ValueError(f"unsupported scenario: {scenario_id!r}; known: {', '.join(SCENARIOS)}")


__all__ = ["SCENARIOS", "scenario_for"]
