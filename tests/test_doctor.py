from __future__ import annotations

from pathlib import Path

import pytest

from nemisis.doctor import doctor


def test_local_doctor_exercises_the_real_crash_prerequisites() -> None:
    result = doctor()

    assert result["status"] == "READY"
    assert {item["name"] for item in result["checks"]} == {
        "python",
        "posix-sigkill",
        "sqlite-wal-full",
    }


def test_live_doctor_reports_every_missing_prerequisite_without_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in (
        "NEBIUS_API_KEY",
        "CONTREE_PROFILE",
        "CONTREE_HOME",
        "NEMISIS_CONTREE_ROOT_IMAGE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    result = doctor("live")
    checks = {item["name"]: item["status"] for item in result["checks"]}

    assert result["status"] == "BLOCKED"
    assert checks["nebius-credential"] == "BLOCKED"
    assert checks["contree-profile"] == "BLOCKED"
    assert checks["immutable-root-image"] == "BLOCKED"
    assert checks["crashcheck-provider-transport"] == "BLOCKED"
    assert "NEBIUS_API_KEY=" not in str(result)


def test_live_doctor_remains_blocked_when_every_external_prerequisite_is_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", "synthetic-secret")
    monkeypatch.setenv("CONTREE_PROFILE", "synthetic-profile")
    monkeypatch.setenv("NEMISIS_CONTREE_ROOT_IMAGE", "00000000-0000-4000-8000-000000000001")

    result = doctor("live")
    checks = {item["name"]: item for item in result["checks"]}

    assert result["status"] == "BLOCKED"
    assert checks["nebius-credential"]["status"] == "PASS"
    assert checks["contree-profile"]["status"] == "PASS"
    assert checks["immutable-root-image"]["status"] == "PASS"
    assert checks["crashcheck-provider-transport"] == {
        "name": "crashcheck-provider-transport",
        "status": "BLOCKED",
        "detail": "CrashCheck live provider transport is not implemented",
    }
    assert "synthetic-secret" not in str(result)
