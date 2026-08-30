from __future__ import annotations

from pathlib import Path

import pytest

from nemisis.junit import MAX_JUNIT_BYTES, parse_junit
from nemisis.models import Outcome


def _report(tmp_path: Path, cases: str) -> Path:
    path = tmp_path / "report.xml"
    path.write_text(f"<testsuite>{cases}</testsuite>")
    return path


def _case(test_id: str, outcome: str, child: str = "") -> str:
    return f"""
    <testcase>
      <properties>
        <property name="nemisis_id" value="{test_id}" />
        <property name="nemisis_outcome" value="{outcome}" />
      </properties>
      {child}
    </testcase>
    """


def test_parses_trusted_outcomes_and_structural_precedence(tmp_path: Path) -> None:
    report = _report(
        tmp_path,
        _case("pass", "PASS")
        + _case("assertion", "ASSERTION_FAIL", "<failure />")
        + _case("exception", "ERROR", "<failure />")
        + _case("error", "ASSERTION_FAIL", "<failure /><error />")
        + _case("skip", "PASS", "<failure /><skipped />"),
    )

    assert parse_junit(report, {"pass", "assertion", "exception", "error", "skip"}) == {
        "pass": Outcome.PASS,
        "assertion": Outcome.ASSERTION_FAIL,
        "exception": Outcome.ERROR,
        "error": Outcome.ERROR,
        "skip": Outcome.NOT_RUN,
    }


@pytest.mark.parametrize("exit_code", [2, 3, 4, 5])
def test_collection_exit_fails_closed(tmp_path: Path, exit_code: int) -> None:
    report = _report(tmp_path, _case("known", "PASS"))
    assert parse_junit(report, {"known"}, exit_code=exit_code) == {"known": Outcome.ERROR}


def test_missing_result_depends_on_process_state(tmp_path: Path) -> None:
    report = _report(tmp_path, _case("ran", "PASS"))
    assert parse_junit(report, {"ran", "missing"}) == {
        "ran": Outcome.PASS,
        "missing": Outcome.NOT_RUN,
    }
    assert parse_junit(report, {"ran", "missing"}, timed_out=True) == {
        "ran": Outcome.TIMEOUT,
        "missing": Outcome.TIMEOUT,
    }
    assert parse_junit(tmp_path / "absent.xml", {"missing"}) == {"missing": Outcome.ERROR}


def test_malformed_duplicate_unknown_or_unannotated_reports_fail_closed(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.xml"
    malformed.write_text("<testsuite>")
    assert parse_junit(malformed, {"known"}) == {"known": Outcome.ERROR}

    duplicate = _report(tmp_path, _case("known", "PASS") * 2)
    assert parse_junit(duplicate, {"known"}) == {"known": Outcome.ERROR}

    unknown = _report(tmp_path, _case("known", "PASS") + _case("other", "PASS"))
    assert parse_junit(unknown, {"known"}) == {"known": Outcome.ERROR}

    unannotated = _report(tmp_path, "<testcase />" + _case("known", "PASS"))
    assert parse_junit(unannotated, {"known"}) == {"known": Outcome.ERROR}


def test_duplicate_expected_ids_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="duplicates"):
        parse_junit(_report(tmp_path, ""), ["same", "same"])


def test_oversized_report_fails_closed(tmp_path: Path) -> None:
    report = tmp_path / "large.xml"
    report.write_bytes(b" " * (MAX_JUNIT_BYTES + 1))
    assert parse_junit(report, {"known"}) == {"known": Outcome.ERROR}
