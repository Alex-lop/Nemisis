"""The Alpha boundary must name every registered scenario, so a new one cannot land silently."""

from __future__ import annotations

import re
from pathlib import Path

from nemisis.scenarios import SCENARIOS

ROOT = Path(__file__).parents[1]
_COUNT_WORDS = {2: "two", 3: "three", 4: "four", 5: "five"}


def test_alpha_boundary_names_every_registered_scenario_and_store() -> None:
    text = (ROOT / "docs/PRODUCT.md").read_text(encoding="utf-8")
    match = re.search(r"## Alpha boundary\n\n(Supported:.*?)\n\n", text, re.DOTALL)
    assert match is not None, "docs/PRODUCT.md no longer opens Alpha boundary with Supported:"
    paragraph = " ".join(match.group(1).split())
    for scenario_id, scenario in SCENARIOS.items():
        assert f"`{scenario_id}`" in paragraph, f"Alpha boundary omits {scenario_id}"
        store = scenario.store_class.__name__
        assert f"`{store}`" in paragraph, f"Alpha boundary omits {store}"
    counted = f"the {_COUNT_WORDS[len(SCENARIOS)]} registered scenarios"
    assert counted in paragraph, f"Alpha boundary should say {counted!r}"
