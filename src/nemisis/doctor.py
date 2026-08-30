"""Independent, secret-free CrashCheck prerequisite checks."""

from __future__ import annotations

import os
import signal
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path
from typing import TypedDict


class Check(TypedDict):
    name: str
    status: str
    detail: str


class DoctorResult(TypedDict):
    mode: str
    status: str
    checks: list[Check]


def doctor(mode: str = "local") -> DoctorResult:
    """Return every prerequisite result; one failure never hides another."""
    if mode not in {"local", "live"}:
        raise ValueError("mode must be 'local' or 'live'")
    checks = [_python_check(), _posix_check(), _sqlite_check()]
    if mode == "live":
        checks.extend(
            (_credential_check(), _profile_check(), _image_check(), _live_transport_check())
        )
    return {
        "mode": mode.upper(),
        "status": "READY" if all(item["status"] == "PASS" for item in checks) else "BLOCKED",
        "checks": checks,
    }


def _python_check() -> Check:
    okay = sys.version_info >= (3, 12)
    return _check("python", okay, f"Python {sys.version_info.major}.{sys.version_info.minor}")


def _posix_check() -> Check:
    okay = all(
        (
            os.name == "posix",
            hasattr(os, "killpg"),
            hasattr(os, "setsid"),
            hasattr(signal, "SIGKILL"),
        )
    )
    return _check("posix-sigkill", okay, "process groups and SIGKILL")


def _sqlite_check() -> Check:
    try:
        with tempfile.TemporaryDirectory(prefix="nemisis-doctor-") as temporary:
            path = Path(temporary) / "probe.sqlite3"
            with sqlite3.connect(path) as connection:
                journal = connection.execute("PRAGMA journal_mode=WAL").fetchone()
                connection.execute("PRAGMA synchronous=FULL")
                synchronous = connection.execute("PRAGMA synchronous").fetchone()
                connection.execute("CREATE TABLE probe(value INTEGER NOT NULL)")
                connection.execute("INSERT INTO probe VALUES (1)")
                connection.commit()
                connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
                connection.execute("PRAGMA journal_mode=DELETE").fetchone()
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
                connection.execute("PRAGMA query_only=ON")
                value = connection.execute("SELECT value FROM probe").fetchone()
            okay = (
                journal == ("wal",)
                and synchronous == (2,)
                and value == (1,)
                and not Path(f"{path}-wal").exists()
                and not Path(f"{path}-shm").exists()
            )
    except (OSError, sqlite3.Error):
        okay = False
    return _check("sqlite-wal-full", okay, f"SQLite {sqlite3.sqlite_version}")


def _credential_check() -> Check:
    return _check("nebius-credential", bool(os.environ.get("NEBIUS_API_KEY")), "NEBIUS_API_KEY")


def _profile_check() -> Check:
    profile = os.environ.get("CONTREE_PROFILE")
    if profile:
        return _check("contree-profile", True, "CONTREE_PROFILE configured")
    if home := os.environ.get("CONTREE_HOME"):
        path = Path(home).expanduser() / "auth.ini"
    else:
        config = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
        path = config / "contree" / "auth.ini"
    return _check("contree-profile", path.is_file(), "ConTree auth profile")


def _image_check() -> Check:
    value = os.environ.get("NEMISIS_CONTREE_ROOT_IMAGE", "")
    try:
        uuid.UUID(value)
    except ValueError:
        okay = False
    else:
        okay = bool(value) and not any(character.isspace() for character in value)
    return _check("immutable-root-image", okay, "NEMISIS_CONTREE_ROOT_IMAGE UUID")


def _live_transport_check() -> Check:
    return _check(
        "crashcheck-provider-transport",
        False,
        "CrashCheck live provider transport is not implemented",
    )


def _check(name: str, okay: bool, detail: str) -> Check:
    return {"name": name, "status": "PASS" if okay else "BLOCKED", "detail": detail}
