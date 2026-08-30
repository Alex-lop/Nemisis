"""Fail-closed parsing for trusted Pytest JUnit reports."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path
from xml.etree import ElementTree

from nemisis.models import Outcome

MAX_JUNIT_BYTES = 512_000


def parse_junit(
    report_path: Path,
    expected_ids: Collection[str],
    *,
    timed_out: bool = False,
    exit_code: int | None = 0,
) -> dict[str, Outcome]:
    """Return outcomes for exactly ``expected_ids``, rejecting untrusted structure."""
    expected = set(expected_ids)
    if len(expected) != len(expected_ids):
        raise ValueError("expected_ids contains duplicates")
    if timed_out:
        return dict.fromkeys(expected, Outcome.TIMEOUT)
    if not report_path.is_file() or exit_code in range(2, 6):
        return dict.fromkeys(expected, Outcome.ERROR)
    try:
        if report_path.stat().st_size > MAX_JUNIT_BYTES:
            return dict.fromkeys(expected, Outcome.ERROR)
    except OSError:
        return dict.fromkeys(expected, Outcome.ERROR)

    try:
        root = ElementTree.parse(report_path).getroot()
    except (ElementTree.ParseError, OSError):
        return dict.fromkeys(expected, Outcome.ERROR)

    outcomes: dict[str, Outcome] = {}
    invalid_report = False
    for case in (element for element in root.iter() if _tag(element) == "testcase"):
        test_ids = _properties(case, "nemisis_id")
        markers = _properties(case, "nemisis_outcome")
        if len(test_ids) != 1 or len(markers) != 1:
            invalid_report = True
            continue
        test_id = test_ids[0]
        if test_id not in expected:
            invalid_report = True
            continue
        if test_id in outcomes:
            outcomes[test_id] = Outcome.ERROR
            continue
        outcomes[test_id] = _outcome(case, markers[0])

    if invalid_report:
        return dict.fromkeys(expected, Outcome.ERROR)
    for test_id in expected - outcomes.keys():
        outcomes[test_id] = Outcome.NOT_RUN
    return outcomes


def _properties(case: ElementTree.Element, name: str) -> list[str]:
    return [
        value
        for properties in case
        if _tag(properties) == "properties"
        for prop in properties
        if _tag(prop) == "property"
        and prop.get("name") == name
        and (value := prop.get("value")) is not None
    ]


def _outcome(case: ElementTree.Element, marker: str) -> Outcome:
    children = {_tag(child) for child in case}
    if "error" in children:
        return Outcome.ERROR
    if "skipped" in children:
        return Outcome.NOT_RUN
    if "failure" in children:
        return Outcome.ASSERTION_FAIL if marker == Outcome.ASSERTION_FAIL else Outcome.ERROR
    return Outcome.PASS if marker == Outcome.PASS else Outcome.ERROR


def _tag(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]
