"""The one CONTRIBUTING.md promise nothing else in the suite holds to account.

"It exits `1` on any disagreement" is the line the nightly red team rests on. Every test in
tests/test_redteam.py calls the library ``run()`` directly and asserts agreement, so the CLI's
failure branch never runs: invert or delete it and the whole suite stays green while the nightly
job goes silently green forever. These two tests drive ``nemisis redteam`` through the CLI with a
stubbed generator, one disagreeing case and one agreeing one, and pin the exit code either way.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import nemisis.cli as cli
import nemisis.redteam as redteam
from nemisis.redteam import Case, Expected, Op

REASON = "every kill point is covered"
SUMMARY = "leftover credit at the marker boundary"


def _case(verdict: str) -> Case:
    return Case(
        index=1,
        ops=(Op.EFFECT, Op.MARK),
        helper=False,
        expected=Expected.PROVEN,
        reason=REASON,
        verdict=verdict,
        summary=SUMMARY,
    )


def _redteam(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: Case) -> None:
    def run(cases: int, seed: int, out: Path, scenario_id: str) -> list[Case]:
        return [case]

    monkeypatch.setattr(redteam, "run", run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "redteam", "--cases", "1", "--out", str(tmp_path / "rt")],
    )
    cli.main()


def test_redteam_exits_one_and_names_the_disagreement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        _redteam(monkeypatch, tmp_path, _case(Expected.STILL_REPRODUCES.value))

    assert error.value.code == 1
    output = capsys.readouterr().out
    assert "1 disagreement" in output
    assert f"case 1: oracle says {REASON}; checker said: {SUMMARY}" in output


def test_redteam_returns_quietly_when_the_oracle_agrees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _redteam(monkeypatch, tmp_path, _case(Expected.PROVEN.value))

    output = capsys.readouterr().out
    assert "0 disagreements" in output
    assert "oracle says" not in output
