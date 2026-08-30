from __future__ import annotations

import sys
from pathlib import Path

import pytest

from nemisis.cli import main
from nemisis.live import live_configuration_blockers


def test_live_mode_lists_blockers_and_never_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in (
        "NEBIUS_API_KEY",
        "NEMISIS_CONTREE_ROOT_IMAGE",
        "CONTREE_PROFILE",
        "CONTREE_HOME",
        "XDG_CONFIG_HOME",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    blockers = live_configuration_blockers()
    assert {message.split()[0] for message in blockers} == {
        "NEBIUS_API_KEY",
        "NEMISIS_CONTREE_ROOT_IMAGE",
        "CONTREE_PROFILE",
    }

    output = tmp_path / "runs"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nemisis",
            "verify",
            "--fixture",
            "idempotency-retry",
            "--mode",
            "live",
            "--output-dir",
            str(output),
        ],
    )
    with pytest.raises(SystemExit, match="LIVE BLOCKED"):
        main()
    assert not output.exists()
