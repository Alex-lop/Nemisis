from __future__ import annotations

from typing import Any

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Any:
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" and report.passed:
        return

    if report.passed:
        nemisis_outcome = "PASS"
    elif report.skipped:
        nemisis_outcome = "NOT_RUN"
    elif call.excinfo is not None and call.excinfo.errisinstance(
        (AssertionError, pytest.fail.Exception)
    ):
        nemisis_outcome = "ASSERTION_FAIL"
    else:
        nemisis_outcome = "ERROR"
    properties = [("nemisis_id", item.name), ("nemisis_outcome", nemisis_outcome)]
    if report.when == "teardown":
        report.user_properties.extend(properties)
    else:
        item.user_properties.extend(properties)
